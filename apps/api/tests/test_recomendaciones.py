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


# ---------- D55: reglas nuevas, acciones del docente y métricas de gestión ----------

def _curso_de_prueba(client, actividades=2):
    """Oferta nueva con estudiante2 matriculado (las DEMO ya suman 100 % de pesos)."""
    admin = auth(client, "ANDINO", "admin@andino.demo")
    users = client.get("/api/v1/users?page_size=100", headers=admin).json()["items"]
    course = client.post("/api/v1/courses", headers=admin, json={
        "code": "TST-2", "title": "Curso de prueba D55",
        "units": [{"title": "Unidad uno", "activities": [{"title": f"Lectura {i + 1}"} for i in range(actividades)]}]}).json()
    client.patch(f"/api/v1/courses/{course['id']}", json={"status": "published"}, headers=admin)
    now = datetime.now(UTC)
    off = client.post("/api/v1/offerings", headers=admin, json={
        "course_id": course["id"], "instructor_id": next(u["id"] for u in users if u["email"] == "docente@andino.demo"),
        "period": "2026-II", "cohort": "Grupo D", "starts_on": (now - timedelta(days=20)).isoformat(),
        "ends_on": (now + timedelta(days=20)).isoformat()}).json()
    student = next(u for u in users if u["email"] == "estudiante2@andino.demo")
    client.post(f"/api/v1/offerings/{off['id']}/enrollments", json={"student_ids": [student["id"]]}, headers=admin)
    return off, course, now


def _recs(client, est, off, history=False):
    return client.get(f"/api/v1/recommendations?offering_id={off['id']}{'&history=true' if history else ''}", headers=est).json()


def test_vencida_y_mejorar_nota(client):
    off, _, now = _curso_de_prueba(client)
    doc = auth(client, "ANDINO", "docente@andino.demo")
    vencida = client.post(f"/api/v1/offerings/{off['id']}/assessments", headers=doc, json={
        "title": "Quiz atrasado", "kind": "opcion_multiple", "weight": 0.2, "due_at": (now - timedelta(days=3)).isoformat()}).json()
    proyecto = client.post(f"/api/v1/offerings/{off['id']}/assessments", headers=doc, json={
        "title": "Proyecto", "kind": "archivo", "weight": 0.3, "max_attempts": 2,
        "due_at": (now + timedelta(days=10)).isoformat()}).json()
    est = auth(client, "ANDINO", "estudiante2@andino.demo")
    client.post(f"/api/v1/assessments/{proyecto['id']}/submissions", json={"answer": "v1"}, headers=est)
    attempt = client.get(f"/api/v1/assessments/{proyecto['id']}/attempts", headers=doc).json()[0]
    client.patch(f"/api/v1/attempts/{attempt['id']}", json={"score": 10}, headers=doc)

    recs = {r["kind"]: r for r in _recs(client, est, off)}
    assert recs["vencida"]["target_id"] == vencida["id"] and "tardía" in recs["vencida"]["reason"]
    assert recs["vencida"]["priority_reason"] == "venció hace 3 días"
    assert "10/20" in recs["mejorar_nota"]["reason"] and "queda 1 intento" in recs["mejorar_nota"]["reason"]
    # Entregar la vencida la cierra como completada, con el motivo.
    client.post(f"/api/v1/assessments/{vencida['id']}/submissions", json={"answer": "tarde"}, headers=est)
    closed = next(r for r in _recs(client, est, off, True) if r["id"] == recs["vencida"]["id"])
    assert closed["status"] == "completada" and closed["resolution_note"] == "La entregaste."


def test_cerca_del_certificado_y_anuncio_sin_leer(client):
    off, course, _ = _curso_de_prueba(client, actividades=4)
    est = auth(client, "ANDINO", "estudiante2@andino.demo")
    acts = [a["id"] for u in client.get(f"/api/v1/offerings/{off['id']}", headers=est).json()["units"] for a in u["activities"]]
    for act in acts[:3]:  # 75 % del curso
        client.post("/api/v1/learning-events", headers=est, json={
            "event_id": str(uuid.uuid4()), "offering_id": off["id"], "activity_id": act, "event_type": "activity_completed"})
    cert = next(r for r in _recs(client, est, off) if r["kind"] == "certificado")
    assert "75 %" in cert["reason"] and "1 actividad obligatoria" in cert["reason"]

    doc = auth(client, "ANDINO", "docente@andino.demo")
    client.post(f"/api/v1/offerings/{off['id']}/community/posts", headers=doc,
                json={"kind": "anuncio", "title": "Repaso del jueves", "body": "Nos vemos a las 7 p. m."})
    anuncio = next(r for r in _recs(client, est, off) if r["kind"] == "anuncio")
    assert anuncio["title"] == "Repaso del jueves" and anuncio["target_type"] == "post"
    client.post(f"/api/v1/recommendations/{anuncio['id']}/feedback", json={"action": "aceptar"}, headers=est)
    closed = next(r for r in _recs(client, est, off, True) if r["id"] == anuncio["id"])
    assert closed["status"] == "completada" and closed["resolution_note"] == "Leíste el anuncio."


def test_competencia_con_nota_baja(client):
    """Con nota baja en una evaluación vinculada a una competencia se sugiere fortalecerla, aclarando que no es oficial.
    Una validación del docente por encima de elemental la cierra (el nivel oficial manda, D34)."""
    off, course, now = _curso_de_prueba(client)
    admin = auth(client, "ANDINO", "admin@andino.demo")
    doc = auth(client, "ANDINO", "docente@andino.demo")
    area = client.post("/api/v1/skills", headers=admin, json={"code": "TST-AREA", "name": "Área de prueba"}).json()
    skill = client.post("/api/v1/skills", headers=admin, json={
        "code": "TST-SK", "name": "Competencia de prueba", "parent_id": area["id"]}).json()
    client.put(f"/api/v1/courses/{course['id']}/skills", headers=admin, json=[{"skill_id": skill["id"]}])
    a = client.post(f"/api/v1/offerings/{off['id']}/assessments", headers=doc, json={
        "title": "Quiz de la competencia", "kind": "opcion_multiple", "weight": 0.4,
        "due_at": (now + timedelta(days=10)).isoformat()}).json()
    client.put(f"/api/v1/assessments/{a['id']}/skills", headers=doc, json=[skill["id"]])
    est = auth(client, "ANDINO", "estudiante2@andino.demo")
    client.post(f"/api/v1/assessments/{a['id']}/submissions", json={"answer": "x"}, headers=est)
    attempt = client.get(f"/api/v1/assessments/{a['id']}/attempts", headers=doc).json()[0]
    client.patch(f"/api/v1/attempts/{attempt['id']}", json={"score": 3}, headers=doc)

    comp = next(r for r in _recs(client, est, off) if r["kind"] == "competencia")
    assert comp["target_id"] == skill["id"] and "Competencia de prueba" in comp["title"] and "orientativa" in comp["reason"]
    client.post("/api/v1/skills/validations", headers=doc, json={
        "student_id": attempt["student_id"], "skill_id": skill["id"], "level": 4, "note": "Lo demostró en clase."})
    closed = next(r for r in _recs(client, est, off, True) if r["id"] == comp["id"])
    assert closed["status"] == "completada" and closed["resolution_note"] == "Tu nivel subió."


def test_acciones_sugeridas_para_el_docente(client):
    doc = auth(client, "ANDINO", "docente@andino.demo")
    actions = client.get("/api/v1/recommendations/teacher-actions", headers=doc).json()
    assert actions and {a["kind"] for a in actions} & {"inactivos", "por_calificar", "sin_entregar", "competencia_grupo"}
    assert all(a["course"] and a["link"].startswith("/") and a["count"] > 0 for a in actions)
    assert [a["priority"] for a in actions] == sorted((a["priority"] for a in actions), reverse=True)
    py = _offering(client, doc, "PY-101")
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")  # no ve las acciones de grupos ajenos
    assert py["id"] not in {a["offering_id"] for a in client.get("/api/v1/recommendations/teacher-actions", headers=doc2).json()}
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get("/api/v1/recommendations/teacher-actions", headers=est).status_code == 403


def test_metricas_de_gestion_por_semana_curso_y_motivo(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    recs = client.get("/api/v1/recommendations", headers=est).json()
    client.post(f"/api/v1/recommendations/{recs[0]['id']}/feedback", json={"action": "descartar", "reason": "ya lo hice"}, headers=est)
    admin = auth(client, "ANDINO", "admin@andino.demo")
    data = client.get("/api/v1/recommendations/insights", headers=admin).json()
    assert data["weekly"] and sum(w["discarded"] for w in data["weekly"]) == 1
    assert data["by_course"] and data["discard_reasons"] == [{"reason": "Ya lo hice", "count": 1}]
    assert client.get("/api/v1/recommendations/insights", headers=est).status_code == 403
