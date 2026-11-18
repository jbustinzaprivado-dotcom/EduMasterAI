"""Recomendaciones (§4.5, §4.11): explicación, estados, feedback, vista docente y métricas."""

import uuid
from datetime import UTC, datetime, timedelta

from tests.conftest import auth


def _offering(client, headers, code):
    return next(o for o in client.get("/api/v1/offerings", headers=headers).json() if o["course_code"] == code)


def test_estudiante_inactiva_recibe_retomar_explicado_sin_ver_su_riesgo(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")  # perfil DEMO en riesgo: lleva semanas sin entrar
    recs = client.get("/api/v1/recommendations", headers=est).json()
    kinds = {r["kind"] for r in recs}
    assert "retomar" in kinds and len(recs) >= 2  # si la actividad más corta es la siguiente, no se duplica
    retomar = next(r for r in recs if r["kind"] == "retomar")
    assert "días sin actividad" in retomar["reason"] and retomar["expected_impact"]
    assert all("riesgo" not in r["reason"].lower() for r in recs)  # D22
    assert recs[0]["priority"] >= recs[-1]["priority"]  # ordenadas por prioridad


def test_completar_la_actividad_cierra_la_recomendacion(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    retomar = next(r for r in client.get("/api/v1/recommendations", headers=est).json() if r["kind"] == "retomar")
    client.post("/api/v1/learning-events", headers=est, json={
        "event_id": str(uuid.uuid4()), "offering_id": retomar["offering_id"], "activity_id": retomar["target_id"],
        "event_type": "activity_completed"})
    history = client.get("/api/v1/recommendations?history=true", headers=est).json()
    assert next(r for r in history if r["id"] == retomar["id"])["status"] == "completada"
    # Ya no está inactiva: no se vuelve a sugerir retomar.
    assert "retomar" not in {r["kind"] for r in client.get("/api/v1/recommendations", headers=est).json()}


def test_aceptar_valorar_y_descartar(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    recs = client.get("/api/v1/recommendations", headers=est).json()
    first, second = recs[0], recs[1]
    url = "/api/v1/recommendations/{}/feedback"
    assert client.post(url.format(first["id"]), json={"action": "aceptar"}, headers=est).json()["status"] == "aceptada"
    assert client.post(url.format(first["id"]), json={"action": "util"}, headers=est).json()["useful"] is True
    r = client.post(url.format(second["id"]), json={"action": "descartar", "reason": "Ya lo repasé"}, headers=est).json()
    assert r["status"] == "descartada"
    # Lo descartado no vuelve a insistirse al refrescar.
    assert second["id"] not in {x["id"] for x in client.get("/api/v1/recommendations", headers=est).json()}
    assert client.post(url.format(second["id"]), json={"action": "aceptar"}, headers=est).status_code == 422
    # Nadie más puede responder por el estudiante.
    otro = auth(client, "ANDINO", "estudiante2@andino.demo")
    assert client.post(url.format(first["id"]), json={"action": "util"}, headers=otro).status_code == 404

    admin = auth(client, "ANDINO", "admin@andino.demo")
    m = client.get("/api/v1/recommendations/metrics", headers=admin).json()
    assert sum(k["aceptada"] + k["descartada"] for k in m) == 2
    assert client.get("/api/v1/recommendations/metrics", headers=est).status_code == 403


def test_entrega_proxima_y_su_cierre(client):
    # Las ofertas DEMO ya suman 100 % de pesos: se abre una oferta nueva con una evaluación que vence en 3 días.
    admin = auth(client, "ANDINO", "admin@andino.demo")
    doc = auth(client, "ANDINO", "docente@andino.demo")
    users = client.get("/api/v1/users?page_size=100", headers=admin).json()["items"]
    course = client.post("/api/v1/courses", headers=admin, json={
        "code": "TST-1", "title": "Curso de prueba",
        "units": [{"title": "Unidad uno", "activities": [{"title": "Lectura uno"}, {"title": "Lectura dos"}]}]}).json()
    client.patch(f"/api/v1/courses/{course['id']}", json={"status": "published"}, headers=admin)
    now = datetime.now(UTC)
    off = client.post("/api/v1/offerings", headers=admin, json={
        "course_id": course["id"], "instructor_id": next(u["id"] for u in users if u["email"] == "docente@andino.demo"),
        "period": "2026-II", "cohort": "Grupo T", "starts_on": (now - timedelta(days=10)).isoformat(),
        "ends_on": (now + timedelta(days=30)).isoformat()}).json()
    student = next(u for u in users if u["email"] == "estudiante2@andino.demo")
    client.post(f"/api/v1/offerings/{off['id']}/enrollments", json={"student_ids": [student["id"]]}, headers=admin)
    a = client.post(f"/api/v1/offerings/{off['id']}/assessments", headers=doc, json={
        "title": "Tarea corta", "kind": "practica", "weight": 0.3,
        "due_at": (now + timedelta(days=3)).isoformat()}).json()

    est = auth(client, "ANDINO", "estudiante2@andino.demo")
    recs = client.get(f"/api/v1/recommendations?offering_id={off['id']}", headers=est).json()
    entrega = next(r for r in recs if r["kind"] == "entrega_proxima")
    assert entrega["target_id"] == a["id"] and "30 %" in entrega["reason"]
    client.post(f"/api/v1/assessments/{a['id']}/submissions", json={"answer": "Listo"}, headers=est)
    history = client.get(f"/api/v1/recommendations?offering_id={off['id']}&history=true", headers=est).json()
    assert next(r for r in history if r["id"] == entrega["id"])["status"] == "completada"


def test_vista_docente_del_grupo(client):
    doc = auth(client, "ANDINO", "docente@andino.demo")
    py = _offering(client, doc, "PY-101")
    recs = client.get(f"/api/v1/offerings/{py['id']}/recommendations", headers=doc).json()
    assert recs and all(r["student_name"] for r in recs)
    assert "Valeria Mendoza" in {r["student_name"] for r in recs}
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")
    assert client.get(f"/api/v1/offerings/{py['id']}/recommendations", headers=doc2).status_code == 404
    analista = auth(client, "ANDINO", "analista@andino.demo")
    assert client.get(f"/api/v1/offerings/{py['id']}/recommendations", headers=analista).status_code == 403
