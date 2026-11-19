# Prueba de carga · escenario «estres» (Fase 7, D43)

- Fecha: 2026-11-19 00:08 · API: `http://127.0.0.1:8010` · base SQLite DEMO, un proceso uvicorn, mismo PC.
- Usuarios virtuales concurrentes: **40** durante **61 s**, con pausas de 0.2–1 s entre acciones.
- Conexiones de notificaciones en vivo (SSE) abiertas a la vez: **20/20**.
- Peticiones HTTP: **4306** (70.3 por segundo) · errores 5xx: **0** · códigos: 200: 4306.

## Resultado frente a §10.5 (milisegundos)

| Operación | Muestras | p50 | p95 | p99 | máx. | Objetivo p95 | Cumple | Errores |
|---|---|---|---|---|---|---|---|---|
| dashboard | 550 | 1297 | 2582 | 3277 | 4407 | 2500 | ❌ | 0 |
| lectura | 1001 | 359 | 1386 | 2271 | 3266 | 500 | ❌ | 0 |
| inferencia | 5 | 422 | 1031 | 1031 | 1031 | 800 | ❌ | 0 |

"Dashboard" es el tiempo hasta tener **todas** las peticiones de la pantalla de Resumen (en paralelo, como el navegador).

## Rutas más lentas según /system/metrics (p95 en ms, vista del servidor)

| Ruta | Peticiones | p95 |
|---|---|---|
| `/api/v1/ml/predictions/run` | 10 | 186.5 |
| `/api/v1/notifications/stream` | 40 | 109.4 |
| `/api/v1/analytics/overview` | 12 | 93.3 |
| `/api/v1/offerings` | 338 | 63.4 |
| `/api/v1/dashboard/summary` | 1108 | 36.8 |
| `/api/v1/dashboard/progress-series` | 776 | 27.5 |
| `/api/v1/notifications` | 1115 | 26.6 |
| `/api/v1/ml/models` | 2 | 20.3 |

## Lectura

- Los objetivos de §10.5 son "iniciales sujetos a pruebas": esta medición es la línea base del PC de la demo.
- El cuello de botella esperado es SQLite (un solo escritor). Con PostgreSQL y varios workers de uvicorn la
  capacidad crece; la arquitectura no cambia (D11).
- Repetir: `python scripts/carga.py --escenario estres --usuarios 40 --segundos 60
  --pausa-min 0.2 --pausa-max 1` con la API en marcha.
