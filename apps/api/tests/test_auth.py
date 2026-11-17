"""Sesión: login, renovación rotatoria, reutilización, cierre y errores normalizados."""

from tests.conftest import auth, login


def test_login_ok_devuelve_token_perfil_y_cookie(client):
    r = login(client, "andino", "Admin@Andino.demo")  # código y correo se normalizan
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900
    assert body["user"]["roles"] == ["admin"]
    assert body["user"]["organization"]["code"] == "ANDINO"
    cookie = r.headers["set-cookie"]
    assert "edumaster_refresh=" in cookie and "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie
    assert "samesite=strict" in cookie.lower()


def test_login_fallido_mensaje_generico_y_auditado(client):
    malas = [
        login(client, "ANDINO", "admin@andino.demo", "incorrecta"),
        login(client, "ANDINO", "noexiste@andino.demo"),
        login(client, "PACIFICO", "admin@andino.demo"),  # correo de otra institución
    ]
    assert {r.status_code for r in malas} == {401}
    assert {r.json()["message"] for r in malas} == {"Institución, correo o contraseña incorrectos."}

    headers = auth(client, "ANDINO", "admin@andino.demo")
    logs = client.get("/api/v1/audit-logs?action=auth.login_failed", headers=headers).json()["items"]
    # El admin de ANDINO no ve intentos sin institución identificada; el superadmin sí.
    assert logs == []
    sa = auth(client, "PLATAFORMA", "superadmin@edumaster.demo")
    assert len(client.get("/api/v1/audit-logs?action=auth.login_failed", headers=sa).json()["items"]) == 3


def test_usuario_desactivado_no_puede_entrar(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    user = client.get("/api/v1/users?q=valeria", headers=admin).json()["items"][0]
    victim = auth(client, "ANDINO", "estudiante@andino.demo")
    r = client.patch(f"/api/v1/users/{user['id']}", json={"status": "disabled"}, headers=admin)
    assert r.status_code == 200
    assert login(client, "ANDINO", "estudiante@andino.demo").status_code == 401
    # Su token de acceso vigente deja de servir de inmediato.
    assert client.get("/api/v1/auth/me", headers=victim).status_code == 401


def test_renovacion_rota_el_token(client):
    login(client, "ANDINO", "docente@andino.demo")
    first = client.cookies.get("edumaster_refresh")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200 and r.json()["user"]["email"] == "docente@andino.demo"
    second = client.cookies.get("edumaster_refresh")
    assert second and second != first


def test_reutilizar_token_viejo_revoca_toda_la_sesion(client):
    login(client, "ANDINO", "docente@andino.demo")
    old = client.cookies.get("edumaster_refresh")
    assert client.post("/api/v1/auth/refresh").status_code == 200
    current = client.cookies.get("edumaster_refresh")

    client.cookies.set("edumaster_refresh", old, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401  # robo detectado
    client.cookies.set("edumaster_refresh", current, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401  # la familia quedó revocada


def test_logout_revoca_la_sesion(client):
    login(client, "ANDINO", "docente@andino.demo")
    raw = client.cookies.get("edumaster_refresh")
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("edumaster_refresh", raw, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_token_invalido_y_error_normalizado_con_correlation_id(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer basura", "X-Correlation-ID": "prueba-123"})
    assert r.status_code == 401
    assert r.json() == {"code": "unauthorized", "message": "Sesión no válida o expirada.", "details": None,
                        "correlation_id": "prueba-123"}
    assert r.headers["X-Correlation-ID"] == "prueba-123"


def test_validacion_devuelve_campos(client):
    r = client.post("/api/v1/auth/login", json={"organization_code": "A", "email": "no-es-correo", "password": "x"})
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["details"]}
    assert {"organization_code", "email"} <= fields


def test_limite_de_intentos(client):
    codes = [login(client, "ANDINO", "admin@andino.demo", "mala").status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
