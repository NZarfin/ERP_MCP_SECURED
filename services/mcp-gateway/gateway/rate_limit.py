"""Per-tenant rate limiting: a fixed-window counter, in this one process's memory.

Explicitly a placeholder (docs/ROADMAP.md Phase 2: "Rate limits, cost budgets,
tool-call audit"): a real deployment runs multiple gateway replicas
(ARCHITECTURE.md §3: "gateway ... stateless, horizontally scaled"), so counts need
to live in Redis or similar, not a process dict. That's commercial-readiness
territory (Phase 8) -- this proves the mechanism and is enough for one process.
"""

import time

DEFAULT_LIMIT_PER_MINUTE = 30


class RateLimiter:
    def __init__(self, limit_per_minute: int = DEFAULT_LIMIT_PER_MINUTE) -> None:
        self._limit = limit_per_minute
        self._windows: dict[str, tuple[int, int]] = {}

    def check(self, tenant_id: str) -> bool:
        """True if this call is allowed; False if the tenant is over the limit
        for the current one-minute window."""
        now_minute = int(time.time() // 60)
        window_start, count = self._windows.get(tenant_id, (now_minute, 0))
        if window_start != now_minute:
            window_start, count = now_minute, 0
        count += 1
        self._windows[tenant_id] = (window_start, count)
        return count <= self._limit


rate_limiter = RateLimiter()
