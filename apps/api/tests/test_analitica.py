"""Analítica educativa y exportación (§4.4): indicadores definidos, filtros, permisos y auditoría."""

import io
from datetime import UTC, datetime, timedelta

from tests.conftest import auth


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def test_resumen_con_definiciones_y_desglose(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    data = client.get("/api/v1/analytics/overview", headers=admin).json()
    assert set(data["definitions"]) >= {"participation_rate", "active_hours", "on_time_rate", "avg_grade"}
    assert all(d["definition"] for d in data["definitions"].values())
    t = data["totals"]
    assert t["enrolled"] == 27 and 0 < t["participation_rate"] <= 1 and t["active_hours"] > 0
    assert {r["course_code"] for r in data["by_offering"]} == {"PY-101", "DS-201", "ML-301"}
    assert data["students_visible"] and len(data["students"]) == 27
    assert data["weekly"] and data["filters"]["desde"]


def test_filtros_por_oferta_y_rango(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    base = client.get("/api/v1/analytics/overview", headers=admin).json()
    ds = next(o for o in base["options"]["offerings"] if o["label"].startswith("DS-201"))
    only = client.get(f"/api/v1/analytics/overview?offering_id={ds['id']}", headers=admin).json()
    assert [r["course_code"] for r in only["by_offering"]] == ["DS-201"] and only["totals"]["enrolled"] == 8
    assert only["filters"]["oferta"].startswith("DS-201")
    now = datetime.now(UTC)
    old = client.get("/api/v1/analytics/overview", headers=admin, params={
        "date_from": _iso(now - timedelta(days=400)), "date_to": _iso(now - timedelta(days=300))}).json()
    assert old["totals"]["active_hours"] == 0 and old["totals"]["submissions"] == 0
    bad = client.get("/api/v1/analytics/overview", headers=admin, params={"date_from": _iso(now), "date_to": _iso(now - timedelta(days=1))})
    assert bad.status_code == 422


def test_permisos_y_alcance(client):
    analista = auth(client, "ANDINO", "analista@andino.demo")
    data = client.get("/api/v1/analytics/overview", headers=analista).json()
    assert data["students"] is None and not data["students_visible"]  # solo agregados (§3)
    assert client.get("/api/v1/analytics/export?level=students", headers=analista).status_code == 403
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")
    mine = client.get("/api/v1/analytics/overview", headers=doc2).json()
    assert [r["course_code"] for r in mine["by_offering"]] == ["DS-201"]
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get("/api/v1/analytics/overview", headers=est).status_code == 403
    pac = auth(client, "PACIFICO", "admin@pacifico.demo")
    assert {r["course_code"] for r in client.get("/api/v1/analytics/overview", headers=pac).json()["by_offering"]} == {"ATN-100"}


def test_exportaciones_con_filtros_y_auditoria(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    r = client.get("/api/v1/analytics/export?format=csv&level=offerings", headers=admin)
    text = r.content.decode("utf-8-sig")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "Generado (UTC):" in text and "Filtros: desde=" in text and "PY-101" in text and "Participación" in text

    x = client.get("/api/v1/analytics/export?format=xlsx&level=students", headers=admin)
    from openpyxl import load_workbook

    ws = load_workbook(io.BytesIO(x.content)).active
    values = [c for row in ws.iter_rows(values_only=True) for c in row if c]
    assert "Estudiante" in values and "Valeria Mendoza" in values

    p = client.get("/api/v1/analytics/export?format=pdf", headers=admin)
    assert p.content.startswith(b"%PDF") and p.headers["content-type"] == "application/pdf"

    logs = client.get("/api/v1/audit-logs?action=analytics.exported", headers=admin).json()["items"]
    assert [l["details"]["format"] for l in logs][:3] == ["pdf", "xlsx", "csv"]
    assert logs[1]["details"]["level"] == "students" and logs[1]["details"]["rows"] == 27
