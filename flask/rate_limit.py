"""A small in-memory rate limiter: enough for the single process that serves the app (one gunicorn worker)"""
import math
import re
import time
from collections import deque
from typing import Callable, Optional

WINDOWS = {'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400}


def parse_rate(value: Optional[str], default: str) -> Optional[tuple[int, int]]:
    """'20/hour' -> (20, 3600). None when the limit is turned off ('0', 'off', 'false', 'none')."""
    text = (value if value is not None else default).strip().lower()
    if text in ('', '0', 'off', 'false', 'none', 'no'):
        return None
    match = re.fullmatch(r'(\d+)\s*/\s*(second|minute|hour|day)', text)
    if not match or int(match.group(1)) == 0:
        raise ValueError(f'Invalid rate limit {value!r}: expected something like 20/hour, or 0 to turn it off')
    return int(match.group(1)), WINDOWS[match.group(2)]


class RateLimiter:
    """Allows `limit` hits per key over a sliding window of `window` seconds"""

    # Above this many keys, the ones without recent hits are forgotten, so that memory stays bounded
    MAX_KEYS = 10_000

    def __init__(self, limit: int, window: int, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self.hits: dict[str, deque] = {}

    def hit(self, key: str) -> Optional[int]:
        """Records a hit. Returns None if it is allowed, or the number of seconds to wait if it is refused."""
        now = self.clock()
        hits = self.hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1, math.ceil(hits[0] + self.window - now))
        hits.append(now)
        if len(self.hits) > self.MAX_KEYS:
            self.__forget_old_keys(now)
        return None

    def __forget_old_keys(self, now: float) -> None:
        for key in [key for key, hits in self.hits.items() if not hits or hits[-1] <= now - self.window]:
            del self.hits[key]
