"""Core académico: visibilidad por rol, eventos idempotentes, progreso, entregas y notas oficiales."""

import uuid
from datetime import UTC, datetime, timedelta

from tests.conftest import auth


def _offering(client, headers, code):
    return next(o for o in client.get("/api/v1/offerings", headers=headers).json() if o["course_code"] == code)


def test_cada_rol_ve_solo_sus_ofertas(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert [o["course_code"] for o in client.get("/api/v1/offerings", headers=est).json()] == ["PY-101"]
    doc = auth(client, "ANDINO", "docente@andino.demo")
    assert sorted(o["course_code"] for o in client.get("/api/v1/offerings", headers=doc).json()) == ["ML-301", "PY-101"]
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")
    assert [o["course_code"] for o in client.get("/api/v1/offerings", headers=doc2).json()] == ["DS-201"]
    admin = auth(client, "ANDINO", "admin@andino.demo")
    assert len(client.get("/api/v1/offerings", headers=admin).json()) == 3
    # Otra institución: la oferta no existe para ella.
    py = _offering(client, admin, "PY-101")
    pac = auth(client, "PACIFICO", "admin@pacifico.demo")
    assert client.get(f"/api/v1/offerings/{py['id']}", headers=pac).status_code == 404


def test_analista_ve_agregados_pero_no_notas_individuales(client):
    analista = auth(client, "ANDINO", "analista@andino.demo")
    py = _offering(client, analista, "PY-101")
    assert py["enrolled"] == 13 and py["avg_progress"] is not None
    assert client.get(f"/api/v1/offerings/{py['id']}/enrollments", headers=analista).status_code == 403
    doc = auth(client, "ANDINO", "docente@andino.demo")
    roster = client.get(f"/api/v1/offerings/{py['id']}/enrollments", headers=doc).json()
    assert len(roster) == 13 and all(0 <= r["progress"] <= 1 for r in roster)


def test_evento_idempotente_actualiza_progreso(client):
    # La historia DEMO es aleatoria: se elige un estudiante que aún tenga actividades pendientes.
    doc = auth(client, "ANDINO", "docente@andino.demo")
    roster = client.get(f"/api/v1/offerings/{_offering(client, doc, 'PY-101')['id']}/enrollments", headers=doc).json()
    email = next(r["student_email"] for r in roster if r["progress"] < 1)
    est = auth(client, "ANDINO", email)
    py = _offering(client, est, "PY-101")
    detail = client.get(f"/api/v1/offerings/{py['id']}", headers=est).json()
    done = set(detail["my_enrollment"]["completed_activity_ids"])
    pending = [a["id"] for u in detail["units"] for a in u["activities"] if a["id"] not in done]
    before = detail["my_enrollment"]["progress"]

    event = {"event_id": str(uuid.uuid4()), "offering_id": py["id"], "activity_id": pending[0],
             "event_type": "activity_completed", "duration_seconds": 600}
    first = client.post("/api/v1/learning-events", json=event, headers=est).json()
    assert first["duplicate"] is False and first["progress"] > before
    again = client.post("/api/v1/learning-events", json=event, headers=est).json()
    assert again["duplicate"] is True and again["progress"] == first["progress"]


def test_evento_invalido_se_rechaza(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    py = _offering(client, est, "PY-101")
    admin = auth(client, "ANDINO", "admin@andino.demo")
    ds = _offering(client, admin, "DS-201")
    ds_activity = client.get(f"/api/v1/offerings/{ds['id']}", headers=admin).json()["units"][0]["activities"][0]["id"]
    base = {"event_type": "activity_completed", "offering_id": py["id"]}
    # Actividad de otro curso.
    r = client.post("/api/v1/learning-events", json={**base, "event_id": str(uuid.uuid4()), "activity_id": ds_activity}, headers=est)
    assert r.status_code == 422
    # Oferta donde no está matriculado.
    r = client.post("/api/v1/learning-events", json={**base, "event_id": str(uuid.uuid4()), "offering_id": ds["id"]}, headers=est)
    assert r.status_code == 404
    # Fecha futura.
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    r = client.post("/api/v1/learning-events", json={**base, "event_id": str(uuid.uuid4()), "occurred_at": future}, headers=est)
    assert r.status_code == 422
    # Un docente no envía eventos de estudiante.
    doc = auth(client, "ANDINO", "docente@andino.demo")
    assert client.post("/api/v1/learning-events", json={**base, "event_id": str(uuid.uuid4())}, headers=doc).status_code == 403


def test_entrega_y_nota_oficial_del_docente(client):
    doc = auth(client, "ANDINO", "docente@andino.demo")
    py = _offering(client, doc, "PY-101")
    due = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    # Los pesos ya suman 100 %: una evaluación extra se rechaza.
    extra = {"title": "Extra", "kind": "practica", "weight": 0.1, "due_at": due}
    assert client.post(f"/api/v1/offerings/{py['id']}/assessments", json=extra, headers=doc).status_code == 422

    est = auth(client, "ANDINO", "estudiante@andino.demo")
    final = next(a for a in client.get("/api/v1/assessments", headers=est).json() if a["title"] == "Examen final")
    r = client.post(f"/api/v1/assessments/{final['id']}/submissions", json={"answer": "Mi respuesta"}, headers=est)
    assert r.status_code == 201 and r.json()["mine"]["attempts"] == 1
    assert client.post(f"/api/v1/assessments/{final['id']}/submissions", json={"answer": "otra"}, headers=est).status_code == 422

    attempt = next(t for t in client.get(f"/api/v1/assessments/{final['id']}/attempts", headers=doc).json()
                   if t["student_name"] == "Valeria Mendoza")
    assert client.patch(f"/api/v1/attempts/{attempt['id']}", json={"score": 25}, headers=doc).status_code == 422
    graded = client.patch(f"/api/v1/attempts/{attempt['id']}", json={"score": 18, "feedback": "Bien"}, headers=doc).json()
    assert graded["score"] == 18

    # Otro docente no puede calificar en una oferta que no dicta.
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")
    assert client.patch(f"/api/v1/attempts/{attempt['id']}", json={"score": 5}, headers=doc2).status_code == 403
    mine = next(a for a in client.get("/api/v1/assessments", headers=est).json() if a["title"] == "Examen final")
    assert mine["mine"]["best_score"] == 18 and mine["mine"]["feedback"] == "Bien"
    log = client.get("/api/v1/audit-logs?action=grade.recorded", headers=auth(client, "ANDINO", "admin@andino.demo")).json()
    assert log["items"][0]["details"]["score"] == [None, 18.0]


def test_admin_crea_curso_publica_oferta_y_matricula(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    vacio = {"code": "vac-1", "title": "Curso vacío"}
    vac = client.post("/api/v1/courses", json=vacio, headers=admin).json()
    assert client.patch(f"/api/v1/courses/{vac['id']}", json={"status": "published"}, headers=admin).status_code == 422

    body = {"code": "sql-101", "title": "SQL desde cero", "level": "basico",
            "units": [{"title": "Consultas", "activities": [{"title": "SELECT", "kind": "video"}]}]}
    course = client.post("/api/v1/courses", json=body, headers=admin).json()
    assert course["code"] == "SQL-101" and course["activity_count"] == 1
    assert client.post("/api/v1/courses", json=body, headers=admin).status_code == 409
    client.patch(f"/api/v1/courses/{course['id']}", json={"status": "published"}, headers=admin)

    users = client.get("/api/v1/users?page_size=100", headers=admin).json()["items"]
    docente = next(u for u in users if u["email"] == "docente2@andino.demo")
    estudiante = next(u for u in users if u["email"] == "estudiante@andino.demo")
    now = datetime.now(UTC)
    offering = {"course_id": course["id"], "instructor_id": docente["id"], "period": "2027-I", "cohort": "Grupo C",
                "starts_on": now.isoformat(), "ends_on": (now + timedelta(days=60)).isoformat()}
    # Un estudiante no puede ser el docente de la oferta.
    bad = client.post("/api/v1/offerings", json={**offering, "instructor_id": estudiante["id"]}, headers=admin)
    assert bad.status_code == 422
    created = client.post("/api/v1/offerings", json=offering, headers=admin).json()
    r = client.post(f"/api/v1/offerings/{created['id']}/enrollments", json={"student_ids": [estudiante["id"]]}, headers=admin)
    assert r.json() == {"created": 1, "skipped": 0}
    # Un docente no puede matricular a alguien que no es estudiante.
    r = client.post(f"/api/v1/offerings/{created['id']}/enrollments", json={"student_ids": [docente["id"]]}, headers=admin)
    assert r.status_code == 422

    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert "SQL-101" in [o["course_code"] for o in client.get("/api/v1/offerings", headers=est).json()]
    assert client.post("/api/v1/courses", json=body, headers=est).status_code == 403


def test_completar_todas_las_actividades_cierra_el_curso(client):
    est = auth(client, "PACIFICO", "estudiante@pacifico.demo")
    atn = _offering(client, est, "ATN-100")
    detail = client.get(f"/api/v1/offerings/{atn['id']}", headers=est).json()
    result = None
    for unit in detail["units"]:
        for activity in unit["activities"]:
            result = client.post("/api/v1/learning-events", headers=est, json={
                "event_id": str(uuid.uuid4()), "offering_id": atn["id"], "activity_id": activity["id"],
                "event_type": "activity_completed"}).json()
    assert result["progress"] == 1 and result["enrollment_status"] == "completed"


def test_estudiante_demo_tiene_perfil_en_riesgo(client):
    # La historia DEMO deja a estudiante@andino.demo rezagada (sirve para la exposición), en cualquier instalación.
    doc = auth(client, "ANDINO", "docente@andino.demo")
    roster = client.get(f"/api/v1/offerings/{_offering(client, doc, 'PY-101')['id']}/enrollments", headers=doc).json()
    valeria = next(r for r in roster if r["student_email"] == "estudiante@andino.demo")
    assert valeria["progress"] < 0.5 and valeria["status"] == "active"
