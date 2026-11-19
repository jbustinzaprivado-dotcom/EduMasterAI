"""Resumen del panel, paginación de la bitácora y health checks."""

from tests.conftest import auth


def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/health/ready").json() == {"status": "ok", "database": "ok"}


def test_resumen_institucional_con_fuente_y_fecha(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    data = client.get("/api/v1/dashboard/summary", headers=admin).json()
    assert data["scope"] == "institución"
    kpis = {k["key"]: k for k in data["kpis"]}
    assert kpis["students"]["value"] == 13 and kpis["courses"]["value"] == 3
    assert kpis["enrollments"]["value"] == 27 and kpis["learning_hours_30d"]["value"] > 0
    assert 0 <= kpis["completion_rate"]["value"] <= 100
    assert kpis["certificates"]["value"] >= 1 and 0 < kpis["avg_progress"]["value"] <= 100
    assert client.get("/api/v1/dashboard/presence", headers=admin).json() == {"online": 0}
    assert kpis["logins_24h"]["value"] == 1 and kpis["logins_24h"]["previous"] == 0
    assert all(k["source"] and k["updated_at"] for k in data["kpis"])
    assert "organizations" not in kpis


def test_resumen_plataforma_y_personal(client):
    sa = auth(client, "PLATAFORMA", "superadmin@edumaster.demo")
    kpis = {k["key"]: k["value"] for k in client.get("/api/v1/dashboard/summary", headers=sa).json()["kpis"]}
    assert kpis["organizations"] == 2 and kpis["students"] == 14 and kpis["enrollments"] == 28

    est = auth(client, "ANDINO", "estudiante@andino.demo")
    data = client.get("/api/v1/dashboard/summary", headers=est).json()
    assert data["scope"] == "personal"
    assert [k["key"] for k in data["kpis"]] == ["my_courses", "my_progress", "my_hours_7d", "my_logins_24h"]
    assert data["kpis"][0]["value"] == 1


def test_series_y_finalizacion_respetan_el_alcance(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    series = client.get("/api/v1/dashboard/progress-series?weeks=8", headers=admin).json()
    assert len(series) == 8 and sum(p["activities_completed"] for p in series) > 0
    comp = client.get("/api/v1/dashboard/completion", headers=admin).json()
    assert comp["total"] == 27 == comp["completed"] + comp["in_progress"] + comp["not_started"]
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get("/api/v1/dashboard/completion", headers=est).json()["total"] == 1
    # La otra institución no suma datos de ANDINO.
    pac = auth(client, "PACIFICO", "admin@pacifico.demo")
    assert client.get("/api/v1/dashboard/completion", headers=pac).json()["total"] == 1


def test_bitacora_paginada_por_cursor(client):
    for _ in range(4):
        auth(client, "ANDINO", "docente@andino.demo")
    admin = auth(client, "ANDINO", "admin@andino.demo")
    first = client.get("/api/v1/audit-logs?action=auth.login&limit=3", headers=admin).json()
    assert len(first["items"]) == 3 and first["next_cursor"]
    second = client.get(f"/api/v1/audit-logs?action=auth.login&limit=3&cursor={first['next_cursor']}", headers=admin).json()
    assert len(second["items"]) == 2 and second["next_cursor"] is None
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}


def test_arquitectura_neuronal_en_estado_diseno(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    data = client.get("/api/v1/ml/architecture", headers=est).json()
    assert data["status"] == "design" and data["version"] is None  # no aparenta un modelo entrenado
    assert [layer["role"] for layer in data["layers"]][0] == "input"
    assert client.get("/api/v1/ml/architecture").status_code == 401
