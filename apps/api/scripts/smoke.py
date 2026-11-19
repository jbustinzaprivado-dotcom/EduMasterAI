"""Smoke test del despliegue (§16.3 paso 35, Fase 8, decisión D44).

Comprueba en segundos que una instalación en marcha (local o la URL pública del túnel) responde bien:
health, base de datos, web, cabeceras de seguridad, inicio de sesión, panel, modelo y verificación pública.

Uso (desde apps/api):
    python scripts/smoke.py                                         -> http://127.0.0.1:8000
    python scripts/smoke.py --url https://xxxx.trycloudflare.com    -> la demo pública
La contraseña DEMO se lee de .env (EDUMASTER_DEMO_PASSWORD) si no se pasa --password.
Sale con código 0 si todo está bien y 1 si algo falló (sirve para scripts y la CI).
"""

from __future__ import annotations

import argparse
import ssl
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--password")
    ap.add_argument("--org", default="ANDINO")
    ap.add_argument("--email", default="admin@andino.demo")
    args = ap.parse_args()
    password = args.password
    if not password:
        from app.core.config import get_settings

        password = get_settings().demo_password
    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> object:
        t = time.perf_counter()
        try:
            value, detail = fn()
            ok = True
        except Exception as exc:  # cualquier fallo cuenta como rojo, con su motivo
            value, ok, detail = None, False, str(exc)[:120]
        results.append((name, ok, f"{detail} ({(time.perf_counter() - t) * 1000:.0f} ms)"))
        return value

    # Certificados del sistema operativo (no los de certifi): en Windows, certifi puede no validar el certificado
    # del túnel de Cloudflare aunque el navegador sí lo haga.
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=15, follow_redirects=True,
                      verify=ssl.create_default_context()) as c:
        def health():
            r = c.get("/api/v1/health")
            r.raise_for_status()
            return r.json(), f"ambiente {r.json()['environment']}"

        def ready():
            r = c.get("/api/v1/health/ready")
            assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:80]}"
            return None, "base de datos ok"

        def web():
            r = c.get("/")
            assert r.status_code == 200 and '<div id="root">' in r.text, "la web no está compilada (npm run build)"
            for h in ("Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options"):
                assert h in r.headers, f"falta la cabecera {h}"
            return None, "index.html con cabeceras de seguridad"

        def login():
            assert password, "falta la contraseña DEMO (.env o --password)"
            r = c.post("/api/v1/auth/login", json={"organization_code": args.org, "email": args.email, "password": password})
            assert r.status_code == 200, f"HTTP {r.status_code}: {r.json().get('message')}"
            return {"Authorization": f"Bearer {r.json()['access_token']}"}, args.email

        env = check("API viva (/health)", health)
        check("Base de datos (/health/ready)", ready)
        check("Web compilada y cabeceras", web)
        h = check("Inicio de sesión", login)
        if h:
            def summary():
                r = c.get("/api/v1/dashboard/summary", headers=h)
                r.raise_for_status()
                return None, f"{len(r.json()['kpis'])} KPIs"

            def model():
                r = c.get("/api/v1/ml/architecture", headers=h)
                r.raise_for_status()
                return None, f"modelo: {r.json()['status_label']}"

            def verify():
                r = c.get("/api/v1/certificates/verify/NO-EXISTE")
                assert r.status_code in (404, 200), f"HTTP {r.status_code}"
                return None, "verificación pública responde"

            check("Panel de resumen", summary)
            check("Estado del modelo", model)
            check("Verificación pública de certificados", verify)

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"[{'OK' if ok else 'FALLO'}] {name.ljust(width)}  {detail}")
    failed = [n for n, ok, _ in results if not ok]
    if env and isinstance(env, dict) and env.get("environment") not in ("demo", None) and args.url.startswith("https"):
        print("AVISO: la URL pública responde con ambiente distinto de 'demo' (¿se abrió con iniciar.bat?).")
    print("\nTodo en orden." if not failed else f"\n{len(failed)} comprobación(es) fallaron: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
