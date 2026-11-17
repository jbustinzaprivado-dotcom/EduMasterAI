"""Límite de intentos en memoria (§11: rate limiting). Suficiente para una sola instancia de la API."""

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, max_hits: int, window_seconds: int):
        self.max_hits, self.window = max_hits, window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.max_hits:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# 10 intentos de inicio de sesión por minuto y por dirección IP.
login_limiter = SlidingWindowLimiter(max_hits=10, window_seconds=60)
