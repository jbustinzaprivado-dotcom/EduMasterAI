"""Métricas operativas en memoria (§12.1, decisión D41).

Por cada ruta (la plantilla, p. ej. /api/v1/courses/{course_id}, no la URL con identificadores) se guardan las
últimas 2 000 latencias y los conteos por código. Con eso se calculan p50/p95/p99, tasa de error y throughput.
Una sola instancia de la API basta para la demo; con varias se exportaría a Prometheus (mismos nombres).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

_WINDOW = 2_000  # latencias por ruta
_RECENT = 300  # segundos para throughput y tasa de error "ahora"


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))
    return round(s[k], 1)


class Metrics:
    def __init__(self) -> None:
        self.started = time.time()
        self._lock = Lock()
        self._lat: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_WINDOW))
        self._count: dict[str, int] = defaultdict(int)
        self._errors: dict[str, int] = defaultdict(int)
        self._status: dict[str, int] = defaultdict(int)
        self._recent: deque[tuple[float, bool]] = deque(maxlen=50_000)

    def observe(self, route: str, status: int, ms: float) -> None:
        now = time.time()
        with self._lock:
            self._lat[route].append(ms)
            self._count[route] += 1
            self._status[f"{status // 100}xx"] += 1
            if status >= 500:
                self._errors[route] += 1
            self._recent.append((now, status >= 500))

    def reset(self) -> None:
        with self._lock:
            self.__init__()

    def snapshot(self) -> dict:
        now = time.time()
        with self._lock:
            recent = [(t, e) for t, e in self._recent if now - t <= _RECENT]
            all_lat = [v for d in self._lat.values() for v in d]
            routes = [
                {
                    "route": r, "requests": self._count[r], "errors_5xx": self._errors[r],
                    "p50_ms": percentile(list(d), 50), "p95_ms": percentile(list(d), 95),
                    "p99_ms": percentile(list(d), 99),
                }
                for r, d in self._lat.items()
            ]
            total = sum(self._count.values())
            status = dict(self._status)
        routes.sort(key=lambda x: -(x["p95_ms"] or 0))
        return {
            "uptime_seconds": round(now - self.started),
            "requests_total": total,
            "status": status,
            "error_rate_5xx": round(sum(e for _, e in recent) / len(recent), 4) if recent else 0.0,
            "throughput_rpm": round(len(recent) / (_RECENT / 60), 1),
            "latency_ms": {"p50": percentile(all_lat, 50), "p95": percentile(all_lat, 95),
                           "p99": percentile(all_lat, 99)},
            "routes": routes[:25],
        }


metrics = Metrics()
