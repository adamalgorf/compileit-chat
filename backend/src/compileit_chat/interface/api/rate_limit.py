"""A small in-memory sliding-window rate limiter, per client.

Enough to stop one browser tab (or script) from burning the OpenAI budget. It is per
process; several replicas would need a shared store such as Redis.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class SlidingWindowRateLimiter:
    """At most `max_requests` per key within any `window_seconds`. Kept in memory, so the limit is
    per process.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def retry_after(self, key: str) -> float | None:
        """Record a request; None if allowed, else seconds until the next one would be."""
        now = self._clock()
        hits = self._hits[key]
        while hits and hits[0] <= now - self._window:
            hits.popleft()
        if len(hits) >= self._max:
            return hits[0] + self._window - now
        hits.append(now)
        return None
