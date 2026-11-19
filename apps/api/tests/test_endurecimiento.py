"""Fase 7: cabeceras de seguridad, límites de tamaño y de frecuencia, métricas operativas (D40, D41)."""

from app.core import hardening
from app.core.rate_limit import SlidingWindowLimiter
from tests.conftest import auth


def test_cabeceras_de_seguridad(client):
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
    # Swagger UI necesita su CDN: sin CSP estricta, pero con el resto de cabeceras.
    docs = client.get("/api/docs")
    assert "Content-Security-Policy" not in docs.headers and docs.headers["X-Frame-Options"] == "DENY"


def test_cuerpo_demasiado_grande(client):
    r = client.post("/api/v1/auth/login", content=b"x" * 2_000_100, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["code"] == "payload_too_large" and r.json()["correlation_id"]


def test_limite_general_por_ip(client, monkeypatch):
    monkeypatch.setattr(hardening, "api_limiter", SlidingWindowLimiter(max_hits=3, window_seconds=60))
    admin = auth(client, "ANDINO", "admin@andino.demo")  # 1
    assert client.get("/api/v1/auth/me", headers=admin).status_code == 200  # 2
    assert client.get("/api/v1/auth/me", headers=admin).status_code == 200  # 3
    r = client.get("/api/v1/auth/me", headers=admin)
    assert r.status_code == 429 and r.headers["Retry-After"] == "60" and r.json()["code"] == "rate_limited"
    assert client.get("/api/v1/health").status_code == 200  # los health checks no cuentan


def test_metricas_operativas_con_permiso(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    client.get("/api/v1/dashboard/summary", headers=admin)
    data = client.get("/api/v1/system/metrics", headers=admin).json()
    assert data["requests_total"] >= 2 and data["latency_ms"]["p95"] is not None
    routes = {r["route"] for r in data["routes"]}
    assert "/api/v1/dashboard/summary" in routes  # plantilla de ruta, sin identificadores
    assert data["targets"]["api_read_p95_ms"] == 500 and "sse_connections" in data["realtime"]
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get("/api/v1/system/metrics", headers=est).status_code == 403


def test_limite_de_login_por_cuenta_no_bloquea_al_aula(client):
    """D46: fuerza bruta contra una cuenta → 429; un aula entera detrás de la misma IP → todos entran."""
    from tests.conftest import login

    for _ in range(10):
        assert login(client, "ANDINO", "admin@andino.demo", "mala-clave-123").status_code == 401
    r = login(client, "ANDINO", "admin@andino.demo", "mala-clave-123")
    assert r.status_code == 429 and r.json()["code"] == "too_many_requests"
    students = ["estudiante@andino.demo"] + [f"estudiante{i}@andino.demo" for i in range(2, 14)]
    for email in students + ["docente@andino.demo", "docente2@andino.demo", "coordinacion@andino.demo"]:
        assert login(client, "ANDINO", email).status_code == 200, email
