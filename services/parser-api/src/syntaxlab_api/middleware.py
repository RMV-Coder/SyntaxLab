"""Request-size limiting (ASGI middleware) and per-client rate limiting (dependency)."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from syntaxlab_api import errors


class BodySizeLimitMiddleware:
    """Rejects request bodies larger than ``max_bytes`` (declared or actually streamed)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > self.max_bytes:
                    await self._reject(send)
                    return

        received = 0
        rejected = False

        async def limited_receive() -> Message:
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected = True
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            if rejected:
                await self._reject(send)

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": "payload_too_large",
                    "message": f"Request body exceeds {self.max_bytes} bytes.",
                }
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class _BodyTooLarge(Exception):
    pass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """In-process token bucket per client. Adequate for the single-process deployment model."""

    _MAX_CLIENTS = 10_000

    def __init__(self, per_minute: int, burst: int, *, trust_proxy_headers: bool) -> None:
        self.rate = per_minute / 60.0
        self.burst = float(burst)
        self.enabled = per_minute > 0
        self.trust_proxy_headers = trust_proxy_headers
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def client_key(self, request: Request) -> str:
        if self.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        if not self.enabled:
            return
        key = self.client_key(request)
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self._MAX_CLIENTS:
                    self._evict(now)
                bucket = self._buckets[key] = _Bucket(tokens=self.burst, updated=now)
            bucket.tokens = min(self.burst, bucket.tokens + (now - bucket.updated) * self.rate)
            bucket.updated = now
            if bucket.tokens < 1.0:
                retry = max(1, int((1.0 - bucket.tokens) / self.rate) + 1)
                raise errors.RateLimited(
                    "Too many requests. Please slow down.", headers={"Retry-After": str(retry)}
                )
            bucket.tokens -= 1.0

    def _evict(self, now: float) -> None:
        # Drop buckets that have fully refilled; they carry no state worth keeping.
        full_after = self.burst / self.rate if self.rate else 0
        for key in [k for k, b in self._buckets.items() if now - b.updated > full_after]:
            del self._buckets[key]
        if len(self._buckets) >= self._MAX_CLIENTS:
            self._buckets.clear()
