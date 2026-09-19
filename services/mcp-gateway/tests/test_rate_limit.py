"""Pure unit tests for the fixed-window rate limiter -- no database needed."""

from __future__ import annotations

import time

import pytest
from gateway.rate_limit import RateLimiter


def test_allows_up_to_the_limit_then_rejects() -> None:
    limiter = RateLimiter(limit_per_minute=3)
    assert limiter.check("tenant-a") is True
    assert limiter.check("tenant-a") is True
    assert limiter.check("tenant-a") is True
    assert limiter.check("tenant-a") is False


def test_tenants_are_isolated() -> None:
    limiter = RateLimiter(limit_per_minute=1)
    assert limiter.check("tenant-a") is True
    assert limiter.check("tenant-a") is False
    assert limiter.check("tenant-b") is True


def test_new_window_resets_the_count(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RateLimiter(limit_per_minute=1)
    real_time = time.time()
    monkeypatch.setattr(time, "time", lambda: real_time)
    assert limiter.check("tenant-a") is True
    assert limiter.check("tenant-a") is False

    monkeypatch.setattr(time, "time", lambda: real_time + 61)
    assert limiter.check("tenant-a") is True
