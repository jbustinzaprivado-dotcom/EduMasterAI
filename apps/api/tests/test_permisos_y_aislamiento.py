"""RBAC y aislamiento entre instituciones (§3, §13.1 criterio 30)."""

from tests.conftest import auth


def _user_id(client, headers, q):
    return client.get(f"/api/v1/users?q={q}", headers=headers).json()["items"][0]["id"]


def test_admin_solo_ve_su_institucion(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    page = client.get("/api/v1/users?page_size=100", headers=admin).json()
    assert page["total"] == 20
    assert {u["organization_code"] for u in page["items"]} == {"ANDINO"}
    assert [o["code"] for o in client.get("/api/v1/organizations", headers=admin).json()] == ["ANDINO"]


def test_admin_no_puede_tocar_usuarios_de_otra_institucion(client):
    sa = auth(client, "PLATAFORMA", "superadmin@edumaster.demo")
    camila = _user_id(client, sa, "camila")  # estudiante de PACIFICO
    admin = auth(client, "ANDINO", "admin@andino.demo")
    r = client.patch(f"/api/v1/users/{camila}", json={"status": "disabled"}, headers=admin)
    assert r.status_code == 404  # no revela que existe


def test_admin_no_puede_crear_en_otra_institucion_ni_asignar_superadmin(client):
    sa = auth(client, "PLATAFORMA", "superadmin@edumaster.demo")
    pacifico = next(o["id"] for o in client.get("/api/v1/organizations", headers=sa).json() if o["code"] == "PACIFICO")
    admin = auth(client, "ANDINO", "admin@andino.demo")
    nuevo = {"email": "x@andino.demo", "full_name": "Usuario Nuevo", "password": "ClaveSegura-123", "roles": ["docente"]}
    assert client.post("/api/v1/users", json={**nuevo, "organization_id": pacifico}, headers=admin).status_code == 404
    assert client.post("/api/v1/users", json={**nuevo, "roles": ["superadmin"]}, headers=admin).status_code == 403
    assert "superadmin" not in {r["code"] for r in client.get("/api/v1/roles", headers=admin).json()}


def test_admin_crea_usuario_y_queda_auditado(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    body = {"email": "Nuevo.Docente@Andino.demo", "full_name": "Nuevo Docente", "password": "ClaveSegura-123",
            "roles": ["docente"]}
    r = client.post("/api/v1/users", json=body, headers=admin)
    assert r.status_code == 201 and r.json()["email"] == "nuevo.docente@andino.demo"
    assert client.post("/api/v1/users", json=body, headers=admin).status_code == 409

    logs = client.get("/api/v1/audit-logs?action=user.created", headers=admin).json()["items"]
    assert logs[0]["actor_name"] == "Martín Quispe" and logs[0]["resource_id"] == r.json()["id"]


def test_mismo_correo_permitido_en_otra_institucion(client):
    sa = auth(client, "PLATAFORMA", "superadmin@edumaster.demo")
    pacifico = next(o["id"] for o in client.get("/api/v1/organizations", headers=sa).json() if o["code"] == "PACIFICO")
    body = {"email": "admin@andino.demo", "full_name": "Homónimo", "password": "ClaveSegura-123",
            "roles": ["docente"], "organization_id": pacifico}
    assert client.post("/api/v1/users", json=body, headers=sa).status_code == 201


def test_roles_sin_permiso_reciben_403(client):
    estudiante = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get("/api/v1/users", headers=estudiante).status_code == 403
    assert client.post("/api/v1/organizations", json={"code": "X1", "name": "Nueva"}, headers=estudiante).status_code == 403
    auditor = auth(client, "ANDINO", "auditoria@andino.demo")
    assert client.get("/api/v1/users", headers=auditor).status_code == 200  # puede leer
    uid = _user_id(client, auditor, "valeria")
    assert client.patch(f"/api/v1/users/{uid}", json={"status": "disabled"}, headers=auditor).status_code == 403


def test_estudiante_solo_ve_su_propia_actividad(client):
    auth(client, "ANDINO", "admin@andino.demo")
    estudiante = auth(client, "ANDINO", "estudiante@andino.demo")
    items = client.get("/api/v1/audit-logs", headers=estudiante).json()["items"]
    assert items and {i["actor_name"] for i in items} == {"Valeria Mendoza"}


def test_admin_no_puede_desactivarse_ni_quitarse_administracion(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    me = client.get("/api/v1/auth/me", headers=admin).json()["id"]
    assert client.patch(f"/api/v1/users/{me}", json={"status": "disabled"}, headers=admin).status_code == 422
    assert client.patch(f"/api/v1/users/{me}", json={"roles": ["docente"]}, headers=admin).status_code == 422


def test_superadmin_crea_institucion(client):
    sa = auth(client, "PLATAFORMA", "superadmin@edumaster.demo")
    r = client.post("/api/v1/organizations", json={"code": "sur-01", "name": "Instituto del Sur"}, headers=sa)
    assert r.status_code == 201 and r.json()["code"] == "SUR-01"
    assert client.post("/api/v1/organizations", json={"code": "SUR-01", "name": "Otra"}, headers=sa).status_code == 409


def test_cambio_de_roles_auditado(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    uid = _user_id(client, admin, "jorge")
    r = client.patch(f"/api/v1/users/{uid}", json={"roles": ["docente", "coordinador"]}, headers=admin)
    assert r.json()["roles"] == ["coordinador", "docente"]
    log = client.get("/api/v1/audit-logs?action=user.roles_changed", headers=admin).json()["items"][0]
    assert log["details"]["roles"] == [["docente"], ["coordinador", "docente"]]
