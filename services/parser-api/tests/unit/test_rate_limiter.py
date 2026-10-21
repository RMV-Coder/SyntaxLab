from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from syntaxlab_api import errors
from syntaxlab_api.middleware import RateLimiter


def request(host: str = "1.2.3.4", forwarded: str | None = None) -> Any:
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)


def test_burst_then_limited_with_retry_after() -> None:
    limiter = RateLimiter(per_minute=60, burst=3)
    for _ in range(3):
        limiter.check(request())
    with pytest.raises(errors.RateLimited) as info:
        limiter.check(request())
    assert info.value.headers is not None
    assert int(info.value.headers["Retry-After"]) >= 1


def test_clients_are_independent() -> None:
    limiter = RateLimiter(per_minute=60, burst=1)
    limiter.check(request("1.1.1.1"))
    limiter.check(request("2.2.2.2"))
    with pytest.raises(errors.RateLimited):
        limiter.check(request("1.1.1.1"))


def test_forwarded_for_is_ignored() -> None:
    # A client-supplied header must not choose the bucket; proxies are resolved by uvicorn.
    limiter = RateLimiter(per_minute=60, burst=1)
    assert limiter.client_key(request("10.0.0.1", "9.9.9.9")) == "10.0.0.1"


def test_disabled_when_zero() -> None:
    limiter = RateLimiter(per_minute=0, burst=1)
    for _ in range(100):
        limiter.check(request())


def test_refill_over_time(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1000.0]
    monkeypatch.setattr("syntaxlab_api.middleware.time.monotonic", lambda: clock[0])
    limiter = RateLimiter(per_minute=60, burst=1)
    limiter.check(request())
    with pytest.raises(errors.RateLimited):
        limiter.check(request())
    clock[0] += 1.0  # one token per second at 60/min
    limiter.check(request())
