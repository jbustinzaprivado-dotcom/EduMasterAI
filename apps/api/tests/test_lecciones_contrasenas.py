"""Contenido de lecciones (§4.3) y gestión de contraseñas (§11.1)."""

from tests.conftest import DEMO_PASSWORD, auth, login


def _py(client, headers):
    o = next(o for o in client.get("/api/v1/offerings", headers=headers).json() if o["course_code"] == "PY-101")
    return o, client.get(f"/api/v1/offerings/{o['id']}", headers=headers).json()


# ---------- lecciones ----------

def test_estudiante_lee_la_leccion_con_recursos_y_navegacion(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    o, detail = _py(client, est)
    first = detail["units"][0]["activities"][0]
    lesson = client.get(f"/api/v1/offerings/{o['id']}/activities/{first['id']}", headers=est).json()
    assert lesson["title"] == "Instalación del entorno" and "## Objetivo" in lesson["content"]
    assert lesson["resources"][0]["url"].startswith("https://") and lesson["previous_id"] is None and lesson["next_id"]
    assert lesson["can_edit"] is False
    otro = auth(client, "ANDINO", "docente2@andino.demo")  # no ve PY-101
    assert client.get(f"/api/v1/offerings/{o['id']}/activities/{first['id']}", headers=otro).status_code == 404


def test_docente_edita_con_version_y_auditoria(client):
    doc = auth(client, "ANDINO", "docente@andino.demo")
    o, detail = _py(client, doc)
    act = detail["units"][1]["activities"][0]
    url = f"/api/v1/offerings/{o['id']}/activities/{act['id']}"
    before = client.get(url, headers=doc).json()
    assert before["can_edit"]
    r = client.patch(url, headers=doc, json={"content": "## Nuevo\nTexto actualizado.",
                                             "resources": [{"title": "Guía", "url": "https://example.org/guia"}]}).json()
    assert r["content_version"] == before["content_version"] + 1 and r["content_updated_by"] == "Jorge Huamán"
    assert client.patch(url, headers=doc, json={"resources": [{"title": "Malo", "url": "javascript:alert(1)"}]}).status_code == 422
    assert client.patch(url, headers=doc, json={"video_url": "ftp://x.org/v"}).status_code == 422
    assert client.patch(url, headers=doc, json={"content": "## Nuevo\nTexto actualizado."}).status_code == 422  # sin cambios
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.patch(url, headers=est, json={"content": "hackeo"}).status_code == 403
    log = client.get("/api/v1/audit-logs?action=activity.updated", headers=auth(client, "ANDINO", "admin@andino.demo")).json()["items"][0]
    assert set(log["details"]["fields"]) == {"content", "resources"}


# ---------- contraseñas ----------

def test_cambiar_la_propia_contrasena(client):
    est = auth(client, "ANDINO", "estudiante2@andino.demo")
    url = "/api/v1/auth/password"
    assert client.post(url, headers=est, json={"current_password": "mala", "new_password": "OtraClave-2026"}).status_code == 422
    weak = client.post(url, headers=est, json={"current_password": DEMO_PASSWORD, "new_password": "soloLetras"})
    assert weak.status_code == 422 and weak.json()["code"] == "weak_password"
    r = client.post(url, headers=est, json={"current_password": DEMO_PASSWORD, "new_password": "MiNuevaClave-2026"})
    assert r.status_code == 200 and r.json()["access_token"]
    assert login(client, "ANDINO", "estudiante2@andino.demo").status_code == 401
    assert login(client, "ANDINO", "estudiante2@andino.demo", "MiNuevaClave-2026").status_code == 200


def test_restablecimiento_obliga_a_cambiar(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    uid = next(u for u in client.get("/api/v1/users?q=ana", headers=admin).json()["items"])["id"]
    temp = client.post(f"/api/v1/users/{uid}/reset-password", headers=admin).json()["temporary_password"]
    assert login(client, "ANDINO", "estudiante2@andino.demo").status_code == 401  # la anterior ya no sirve

    r = login(client, "ANDINO", "estudiante2@andino.demo", temp)
    assert r.json()["user"]["must_change_password"] is True
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    blocked = client.get("/api/v1/offerings", headers=h)
    assert blocked.status_code == 403 and blocked.json()["code"] == "password_change_required"  # el servidor bloquea
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    ok = client.post("/api/v1/auth/password", headers=h, json={"current_password": temp, "new_password": "ElegidaPorMi-77"}).json()
    assert ok["user"]["must_change_password"] is False
    h2 = {"Authorization": f"Bearer {ok['access_token']}"}
    assert client.get("/api/v1/offerings", headers=h2).status_code == 200
    actions = {i["action"] for i in client.get("/api/v1/audit-logs", headers=admin).json()["items"]}
    assert {"auth.password_reset", "auth.password_changed"} <= actions


def test_restablecer_respeta_permisos(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    me = client.get("/api/v1/auth/me", headers=admin).json()["id"]
    assert client.post(f"/api/v1/users/{me}/reset-password", headers=admin).status_code == 422
    sa = auth(client, "PLATAFORMA", "superadmin@edumaster.demo")
    pac_user = next(u for u in client.get("/api/v1/users?q=camila", headers=sa).json()["items"])["id"]
    assert client.post(f"/api/v1/users/{pac_user}/reset-password", headers=admin).status_code == 404
    doc = auth(client, "ANDINO", "docente@andino.demo")
    assert client.post(f"/api/v1/users/{me}/reset-password", headers=doc).status_code == 403
    nuevo = {"email": "debil@andino.demo", "full_name": "Clave Débil", "password": "1234567890", "roles": ["docente"]}
    assert client.post("/api/v1/users", json=nuevo, headers=admin).json()["code"] == "weak_password"
