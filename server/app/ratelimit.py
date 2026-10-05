"""A small in-memory per-address rate limit (sync contract §2.3: /api/pair, 10 per minute)."""

import threading
from collections import deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float) -> bool:
        """Count one request from ``key``. False once it's over the limit for the window."""
        with self._lock:
            if len(self._hits) > 1024:  # forget quiet addresses so memory stays small
                for stale in [
                    k for k, h in self._hits.items() if not h or now - h[-1] > self.window
                ]:
                    del self._hits[stale]
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True
