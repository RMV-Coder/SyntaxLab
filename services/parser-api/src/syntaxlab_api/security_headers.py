"""Security and caching headers for every API response."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Read-only reference data that changes only with a deployment. Language status is not here: it
# changes while models load.
_CACHEABLE_PREFIXES = (
    "/api/v1/schemes/",
    "/api/v1/grammar/presets",
    "/api/v1/learning/exercises",
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cacheable_route = scope.get("method") == "GET" and str(scope.get("path", "")).startswith(
            _CACHEABLE_PREFIXES
        )

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Only successful reads are shared; errors are never cached.
                cacheable = cacheable_route and message["status"] == 200
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"cache-control", b"public, max-age=300" if cacheable else b"no-store"),
                ]
            await send(message)

        await self.app(scope, receive, send_with_headers)
