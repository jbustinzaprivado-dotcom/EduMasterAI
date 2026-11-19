"""Mapa agregado con supresión de grupos pequeños (§4.1) y comunidad por curso (§4.8)."""

from tests.conftest import auth


def _offering(client, headers, code):
    return next(o for o in client.get("/api/v1/offerings", headers=headers).json() if o["course_code"] == code)


# ---------- mapa ----------

def test_mapa_agrega_y_oculta_grupos_pequenos(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    geo = client.get("/api/v1/dashboard/geo", headers=admin).json()
    regions = {r["region"]: r for r in geo["regions"]}
    assert geo["k"] == 3 and set(regions) == {"Lima", "Arequipa", "Cusco"}
    assert "Junín" not in regions and geo["suppressed_students"] == 2  # 2 estudiantes: no se nombra la región
    assert regions["Lima"]["students"] == 5 and 0 <= regions["Lima"]["avg_progress"] <= 1
    assert set(geo["regions"][0]) == {"region", "students", "avg_progress", "completion_rate"}  # sin nombres


def test_mapa_respeta_alcance_y_rol(client):
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")  # solo DS-201 (8 estudiantes)
    total = sum(r["students"] for r in client.get("/api/v1/dashboard/geo", headers=doc2).json()["regions"])
    assert total <= 8
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get("/api/v1/dashboard/geo", headers=est).status_code == 403
    pac = auth(client, "PACIFICO", "admin@pacifico.demo")
    geo = client.get("/api/v1/dashboard/geo", headers=pac).json()
    assert geo["regions"] == [] and geo["suppressed_students"] == 1  # Piura con 1 persona: oculto


def test_region_invalida_se_rechaza(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    uid = client.get("/api/v1/users?q=valeria", headers=admin).json()["items"][0]["id"]
    assert client.patch(f"/api/v1/users/{uid}", json={"region": "Atlantis"}, headers=admin).status_code == 422
    assert client.patch(f"/api/v1/users/{uid}", json={"region": "Tacna"}, headers=admin).json()["region"] == "Tacna"


# ---------- comunidad ----------

def test_espacio_del_curso_y_permisos(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    py = _offering(client, est, "PY-101")
    space = client.get(f"/api/v1/offerings/{py['id']}/community", headers=est).json()
    assert space["can_post"] and not space["can_announce"] and not space["can_moderate"] and space["rules"]
    assert space["posts"][0]["kind"] == "anuncio"  # anuncios primero
    r = client.post(f"/api/v1/offerings/{py['id']}/community/posts", headers=est,
                    json={"kind": "anuncio", "title": "Anuncio falso", "body": "No debería poder"})
    assert r.status_code == 403
    # Quien no es miembro no ve el espacio: otro docente, analista y otra institución.
    for org, email, code in [("ANDINO", "docente2@andino.demo", 404), ("ANDINO", "analista@andino.demo", 403),
                             ("PACIFICO", "admin@pacifico.demo", 404)]:
        assert client.get(f"/api/v1/offerings/{py['id']}/community", headers=auth(client, org, email)).status_code == code


def test_anuncio_notifica_y_silenciar_lo_evita(client):
    doc = auth(client, "ANDINO", "docente@andino.demo")
    py = _offering(client, doc, "PY-101")
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    otro = auth(client, "ANDINO", "estudiante2@andino.demo")
    client.put(f"/api/v1/offerings/{py['id']}/community/mute", json={"muted": True}, headers=otro)
    r = client.post(f"/api/v1/offerings/{py['id']}/community/posts", headers=doc,
                    json={"kind": "anuncio", "title": "Sesión de repaso", "body": "Jueves 7 p. m."})
    assert r.status_code == 201
    kinds = lambda h: [n["kind"] for n in client.get("/api/v1/notifications", headers=h).json()["items"]]  # noqa: E731
    assert "community.announcement" in kinds(est)
    assert "community.announcement" not in kinds(otro)


def test_debate_comentario_y_respuesta_notificada(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    py = _offering(client, est, "PY-101")
    post = client.post(f"/api/v1/offerings/{py['id']}/community/posts", headers=est,
                       json={"title": "Duda sobre funciones", "body": "¿Cuándo uso return?"}).json()
    doc = auth(client, "ANDINO", "docente@andino.demo")
    thread = client.post(f"/api/v1/community/posts/{post['id']}/comments", json={"body": "Cuando necesites el valor."},
                         headers=doc).json()
    assert thread["comments"][-1]["author_is_teacher"] and thread["post"]["comments"] == 1
    assert any(n["kind"] == "community.reply" for n in client.get("/api/v1/notifications", headers=est).json()["items"])


def test_reporte_y_moderacion_auditada(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    py = _offering(client, est, "PY-101")
    post = client.post(f"/api/v1/offerings/{py['id']}/community/posts", headers=est,
                       json={"title": "Vendo respuestas", "body": "Escríbanme por interno"}).json()
    otro = auth(client, "ANDINO", "estudiante2@andino.demo")
    rep = {"target_type": "post", "target_id": post["id"], "reason": "Promueve copiar en el examen"}
    assert client.post("/api/v1/community/reports", json=rep, headers=otro).status_code == 201
    assert client.post("/api/v1/community/reports", json=rep, headers=otro).status_code == 409

    doc = auth(client, "ANDINO", "docente@andino.demo")
    reports = client.get(f"/api/v1/offerings/{py['id']}/community/reports", headers=doc).json()
    assert reports[0]["target_id"] == post["id"]
    assert client.get(f"/api/v1/offerings/{py['id']}/community/reports", headers=est).status_code == 403
    url = f"/api/v1/community/post/{post['id']}/moderate"
    assert client.post(url, json={"action": "ocultar"}, headers=doc).status_code == 422  # pide motivo
    assert client.post(url, json={"action": "ocultar", "reason": "Incumple la regla 4"}, headers=doc).json()["hidden"]
    assert client.post(url, json={"action": "ocultar", "reason": "x" * 6}, headers=est).status_code == 403

    # El resto ya no lo ve; el moderador sí, con el motivo.
    titles = [p["title"] for p in client.get(f"/api/v1/offerings/{py['id']}/community", headers=otro).json()["posts"]]
    assert "Vendo respuestas" not in titles
    assert client.get(f"/api/v1/community/posts/{post['id']}", headers=otro).status_code == 404
    mod = next(p for p in client.get(f"/api/v1/offerings/{py['id']}/community", headers=doc).json()["posts"] if p["id"] == post["id"])
    assert mod["hidden"] and mod["hidden_reason"] == "Incumple la regla 4"
    assert client.get(f"/api/v1/offerings/{py['id']}/community/reports", headers=doc).json() == []
    admin = auth(client, "ANDINO", "admin@andino.demo")
    log = client.get("/api/v1/audit-logs?action=community.ocultado", headers=admin).json()["items"][0]
    assert log["details"]["reason"] == "Incumple la regla 4"
