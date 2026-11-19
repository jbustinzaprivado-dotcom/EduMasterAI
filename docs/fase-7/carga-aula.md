# Prueba de carga · escenario «aula» (Fase 7, D43)

- Fecha: 2026-11-19 00:07 · API: `http://127.0.0.1:8010` · base SQLite DEMO, un proceso uvicorn, mismo PC.
- Usuarios virtuales concurrentes: **40** durante **98 s**, con pausas de 3–8 s entre acciones.
- Conexiones de notificaciones en vivo (SSE) abiertas a la vez: **20/20**.
- Peticiones HTTP: **1767** (18.0 por segundo) · errores 5xx: **0** · códigos: 200: 1767.

## Resultado frente a §10.5 (milisegundos)

| Operación | Muestras | p50 | p95 | p99 | máx. | Objetivo p95 | Cumple | Errores |
|---|---|---|---|---|---|---|---|---|
| dashboard | 226 | 70 | 919 | 1206 | 1236 | 2500 | ✅ | 0 |
| lectura | 406 | 22 | 512 | 849 | 1075 | 500 | ❌ | 0 |
| inferencia | 5 | 81 | 245 | 245 | 245 | 800 | ✅ | 0 |

"Dashboard" es el tiempo hasta tener **todas** las peticiones de la pantalla de Resumen (en paralelo, como el navegador).

## Rutas más lentas según /system/metrics (p95 en ms, vista del servidor)

| Ruta | Peticiones | p95 |
|---|---|---|
| `/api/v1/offerings` | 97 | 379.9 |
| `/api/v1/analytics/overview` | 1 | 272.1 |
| `/api/v1/ml/predictions/run` | 5 | 186.5 |
| `/api/v1/notifications` | 327 | 161.6 |
| `/api/v1/dashboard/summary` | 318 | 146.7 |
| `/api/v1/notifications/stream` | 20 | 110.1 |
| `/api/v1/dashboard/progress-series` | 226 | 97.3 |
| `/api/v1/dashboard/presence` | 226 | 86.9 |

## Lectura

- Los objetivos de §10.5 son "iniciales sujetos a pruebas": esta medición es la línea base del PC de la demo.
- El cuello de botella esperado es SQLite (un solo escritor). Con PostgreSQL y varios workers de uvicorn la
  capacidad crece; la arquitectura no cambia (D11).
- Repetir: `python scripts/carga.py --escenario aula --usuarios 40 --segundos 90
  --pausa-min 3 --pausa-max 8` con la API en marcha.
