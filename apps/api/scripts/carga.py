"""Prueba de carga contra los objetivos de §10.5 (Fase 7, decisión D43).

Simula usuarios concurrentes (estudiantes, docentes y administración) contra una API en marcha y mide:
- Carga del dashboard: todas las peticiones que hace la pantalla de Resumen, en paralelo (objetivo p95 2,5 s).
- Lectura común: cursos, ofertas, notificaciones, perfil (objetivo p95 500 ms).
- Inferencia: cálculo de riesgo de una oferta (objetivo p95 800 ms).
- Conexiones SSE abiertas a la vez durante toda la prueba (saturación del tiempo real).

Uso: con la API corriendo (p. ej. `python scripts/e2e_server.py`, que trae límites amplios):
    python scripts/carga.py --url http://127.0.0.1:8010 --usuarios 40 --segundos 60 --password ClaveE2E-2026
Escribe el informe en docs/fase-7/prueba-de-carga.md.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
TARGETS = {"dashboard": 2500, "lectura": 500, "inferencia": 800}
DASHBOARD = ["/dashboard/summary", "/dashboard/progress-series?weeks=8", "/dashboard/completion",
             "/ml/architecture", "/dashboard/presence", "/notifications?limit=10"]
READS = ["/offerings", "/notifications?limit=20", "/auth/me", "/dashboard/summary"]
ADMIN_READS = READS + ["/courses", "/audit-logs?limit=20", "/analytics/overview"]


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))] if s else 0.0


class Stats:
    def __init__(self) -> None:
        self.lat: dict[str, list[float]] = defaultdict(list)
        self.errors: dict[str, int] = defaultdict(int)
        self.codes: dict[int, int] = defaultdict(int)

    def add(self, kind: str, ms: float, ok: bool) -> None:
        self.lat[kind].append(ms)
        if not ok:
            self.errors[kind] += 1


async def login(c: httpx.AsyncClient, email: str, password: str) -> dict:
    r = await c.post("/api/v1/auth/login", json={"organization_code": "ANDINO", "email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def get(c: httpx.AsyncClient, path: str, h: dict, stats: Stats) -> bool:
    r = await c.get(f"/api/v1{path}", headers=h)
    stats.codes[r.status_code] += 1
    return r.status_code < 500


async def user_loop(c, h, stats: Stats, until: float, offering: str | None, can_infer: bool, reads: list[str],
                    pause: tuple[float, float]):
    while time.perf_counter() < until:
        roll = random.random()
        t = time.perf_counter()
        if roll < 0.35:  # abrir el dashboard: todas sus peticiones en paralelo
            oks = await asyncio.gather(*(get(c, p, h, stats) for p in DASHBOARD))
            stats.add("dashboard", (time.perf_counter() - t) * 1000, all(oks))
        elif roll < 0.95 or not (can_infer and offering):
            ok = await get(c, random.choice(reads), h, stats)
            stats.add("lectura", (time.perf_counter() - t) * 1000, ok)
        else:
            r = await c.post("/api/v1/ml/predictions/run", json={"offering_id": offering}, headers=h)
            stats.codes[r.status_code] += 1
            stats.add("inferencia", (time.perf_counter() - t) * 1000, r.status_code < 500)
        await asyncio.sleep(random.uniform(*pause))  # tiempo que una persona lee antes de su siguiente clic


async def sse_holder(url: str, h: dict, until: float, counter: list[int]):
    try:
        async with httpx.AsyncClient(base_url=url, timeout=None) as c:
            async with c.stream("GET", "/api/v1/notifications/stream", headers=h) as r:
                if r.status_code == 200:
                    counter[0] += 1
                async for _ in r.aiter_lines():
                    if time.perf_counter() >= until:
                        break
    except Exception:
        pass


async def main(args) -> None:
    limits = httpx.Limits(max_connections=args.usuarios * 3)
    async with httpx.AsyncClient(base_url=args.url, timeout=30, limits=limits) as c:
        admin = await login(c, "admin@andino.demo", args.password)
        models = (await c.get("/api/v1/ml/models", headers=admin)).json()
        if models and not any(m["published_here"] for m in models):
            await c.post(f"/api/v1/ml/models/{models[0]['id']}/approve", json={"note": "prueba de carga"}, headers=admin)
        docente = await login(c, "docente@andino.demo", args.password)
        offerings = (await c.get("/api/v1/offerings", headers=docente)).json()
        offering = offerings[0]["id"] if offerings else None
        pool = [("admin@andino.demo", False), ("coordinacion@andino.demo", False), ("docente@andino.demo", True),
                ("estudiante@andino.demo", False)] + [(f"estudiante{i}@andino.demo", False) for i in range(2, 12)]
        headers = {}
        for email, _ in pool:
            headers[email] = await login(c, email, args.password)

        stats = Stats()
        until = time.perf_counter() + args.segundos
        sse_ok = [0]
        sse = [asyncio.create_task(sse_holder(args.url, headers[pool[i % len(pool)][0]], until, sse_ok))
               for i in range(args.sse)]
        users = []
        for i in range(args.usuarios):
            email, infer = pool[i % len(pool)]
            reads = ADMIN_READS if email.startswith("admin") else READS
            users.append(user_loop(c, headers[email], stats, until, offering, infer, reads,
                                   (args.pausa_min, args.pausa_max)))
        started = time.perf_counter()
        await asyncio.gather(*users)
        elapsed = time.perf_counter() - started
        for t in sse:
            t.cancel()
        ops = (await c.get("/api/v1/system/metrics", headers=admin)).json()

    report(args, stats, elapsed, sse_ok[0], ops)


def report(args, stats: Stats, elapsed: float, sse_ok: int, ops: dict) -> None:
    total = sum(stats.codes.values())
    rows = []
    for kind in ("dashboard", "lectura", "inferencia"):
        v = stats.lat.get(kind, [])
        if not v:
            continue
        p95 = pct(v, 95)
        rows.append(f"| {kind} | {len(v)} | {pct(v, 50):.0f} | {p95:.0f} | {pct(v, 99):.0f} | {max(v):.0f} | "
                    f"{TARGETS[kind]} | {'✅' if p95 <= TARGETS[kind] else '❌'} | {stats.errors.get(kind, 0)} |")
    e5 = sum(n for code, n in stats.codes.items() if code >= 500)
    codes = ", ".join(f"{k}: {v}" for k, v in sorted(stats.codes.items()))
    slow = "\n".join(f"| `{r['route']}` | {r['requests']} | {r['p95_ms']} |" for r in ops.get("routes", [])[:8])
    md = f"""# Prueba de carga · escenario «{args.escenario}» (Fase 7, D43)

- Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')} · API: `{args.url}` · base SQLite DEMO, un proceso uvicorn, mismo PC.
- Usuarios virtuales concurrentes: **{args.usuarios}** durante **{elapsed:.0f} s**, con pausas de {args.pausa_min:g}–{args.pausa_max:g} s entre acciones.
- Conexiones de notificaciones en vivo (SSE) abiertas a la vez: **{sse_ok}/{args.sse}**.
- Peticiones HTTP: **{total}** ({total / elapsed:.1f} por segundo) · errores 5xx: **{e5}** · códigos: {codes}.

## Resultado frente a §10.5 (milisegundos)

| Operación | Muestras | p50 | p95 | p99 | máx. | Objetivo p95 | Cumple | Errores |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

"Dashboard" es el tiempo hasta tener **todas** las peticiones de la pantalla de Resumen (en paralelo, como el navegador).

## Rutas más lentas según /system/metrics (p95 en ms, vista del servidor)

| Ruta | Peticiones | p95 |
|---|---|---|
{slow}

## Lectura

- Los objetivos de §10.5 son "iniciales sujetos a pruebas": esta medición es la línea base del PC de la demo.
- El cuello de botella esperado es SQLite (un solo escritor). Con PostgreSQL y varios workers de uvicorn la
  capacidad crece; la arquitectura no cambia (D11).
- Repetir: `python scripts/carga.py --escenario {args.escenario} --usuarios {args.usuarios} --segundos {args.segundos}
  --pausa-min {args.pausa_min:g} --pausa-max {args.pausa_max:g}` con la API en marcha.
"""
    out = ROOT / "docs" / "fase-7" / f"carga-{args.escenario}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(md.encode("ascii", "replace").decode())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8010")
    ap.add_argument("--usuarios", type=int, default=40)
    ap.add_argument("--segundos", type=int, default=60)
    ap.add_argument("--sse", type=int, default=20)
    ap.add_argument("--password", default="ClaveE2E-2026")
    ap.add_argument("--escenario", default="aula")
    ap.add_argument("--pausa-min", type=float, default=3.0)
    ap.add_argument("--pausa-max", type=float, default=8.0)
    asyncio.run(main(ap.parse_args()))
