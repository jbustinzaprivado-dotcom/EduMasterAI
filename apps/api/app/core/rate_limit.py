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


# Inicio de sesión (D46): 10 intentos por minuto por IP **y correo** (frena la fuerza bruta contra una cuenta) y
# 6 veces eso por IP sola (frena el barrido de muchas cuentas). Así un aula entera detrás del mismo Wi-Fi, que sale
# a Internet con una sola IP, puede entrar a la vez sin bloquearse.
def _login_limit() -> int:
    from app.core.config import get_settings

    return get_settings().login_rate_limit


class LoginLimiter:
    def __init__(self, per_account: int):
        self.account = SlidingWindowLimiter(max_hits=per_account, window_seconds=60)
        self.ip = SlidingWindowLimiter(max_hits=per_account * 6, window_seconds=60)

    def allow(self, ip: str, email: str = "") -> bool:
        return self.account.allow(f"{ip}|{email.strip().lower()}") and self.ip.allow(ip)

    def reset(self) -> None:
        self.account.reset()
        self.ip.reset()


login_limiter = LoginLimiter(per_account=_login_limit())
