"""Rutas de aprendizaje (§4.2): creación, versión, asignación por cohorte, avance, excepciones e historial."""

from datetime import UTC, datetime, timedelta

from tests.conftest import auth


def _courses(client, headers):
    return {c["code"]: c for c in client.get("/api/v1/courses", headers=headers).json()}


def _demo_path(client, headers):
    return next(p for p in client.get("/api/v1/paths", headers=headers).json() if p["code"] == "RUTA-DATOS")


def test_ruta_demo_y_avance_del_estudiante(client):
    coord = auth(client, "ANDINO", "coordinacion@andino.demo")
    path = _demo_path(client, coord)
    assert path["status"] == "published" and [s["course_code"] for s in path["steps"]] == ["PY-101", "DS-201", "ML-301"]
    assert path["assigned"] == 13

    est = auth(client, "ANDINO", "estudiante@andino.demo")  # Valeria: PY-101 en curso, sin DS-201
    mine = client.get("/api/v1/my/paths", headers=est).json()[0]
    statuses = [s["status"] for s in mine["steps"]]
    assert statuses == ["en_curso", "bloqueado", "bloqueado"]  # prerrequisito secuencial
    assert mine["next_step"]["course_code"] == "PY-101" and mine["progress"] == 0
    assert mine["competencies"] and mine["target_date"]


def test_estudiante_que_completo_py101_avanza(client):
    coord = auth(client, "ANDINO", "coordinacion@andino.demo")
    path = _demo_path(client, coord)
    rows = client.get(f"/api/v1/paths/{path['id']}/assignments", headers=coord).json()
    advanced = [r for r in rows if r["completed_steps"] >= 1]
    assert advanced and all(r["progress"] >= 0.33 for r in advanced)
    detail = client.get(f"/api/v1/path-assignments/{advanced[0]['id']}", headers=coord).json()
    assert detail["steps"][0]["status"] == "completado" and detail["steps"][1]["status"] in ("en_curso", "disponible")


def test_crear_publicar_y_versionar_con_historial(client):
    coord = auth(client, "ANDINO", "coordinacion@andino.demo")
    courses = _courses(client, coord)
    body = {"code": "ruta-py", "title": "Python esencial", "objective": "Dominar lo básico de Python y datos.",
            "competencies": ["Python"], "steps": [{"course_id": courses["PY-101"]["id"]}]}
    created = client.post("/api/v1/paths", json=body, headers=coord).json()
    assert created["code"] == "RUTA-PY" and created["status"] == "draft"
    assert client.post("/api/v1/paths", json=body, headers=coord).status_code == 409
    rep = {**body, "code": "rep", "steps": [{"course_id": courses["PY-101"]["id"]}, {"course_id": courses["PY-101"]["id"]}]}
    assert client.post("/api/v1/paths", json=rep, headers=coord).status_code == 422  # curso repetido

    # No se publica con un curso en borrador.
    web = {**body, "code": "web", "steps": [{"course_id": courses["WEB-110"]["id"]}]}
    wid = client.post("/api/v1/paths", json=web, headers=coord).json()["id"]
    assert client.post(f"/api/v1/paths/{wid}/status", json={"status": "published"}, headers=coord).status_code == 422

    pid = created["id"]
    assert client.post(f"/api/v1/paths/{pid}/status", json={"status": "published"}, headers=coord).json()["status"] == "published"
    updated = client.patch(f"/api/v1/paths/{pid}", headers=coord, json={"steps": [
        {"course_id": courses["PY-101"]["id"]}, {"course_id": courses["DS-201"]["id"], "min_grade": 13}]}).json()
    assert updated["version"] == 2 and len(updated["steps"]) == 2
    history = client.get(f"/api/v1/paths/{pid}/history", headers=coord).json()
    assert [h["action"] for h in history][:3] == ["path.updated", "path.published", "path.created"]
    assert history[0]["details"]["steps"] == [["PY-101"], ["PY-101", "DS-201"]]


def test_asignar_por_cohorte_e_individual(client):
    coord = auth(client, "ANDINO", "coordinacion@andino.demo")
    courses = _courses(client, coord)
    pid = client.post("/api/v1/paths", headers=coord, json={
        "code": "R2", "title": "Ruta corta", "objective": "Probar asignaciones de la ruta.",
        "steps": [{"course_id": courses["DS-201"]["id"]}]}).json()["id"]
    assert client.post(f"/api/v1/paths/{pid}/assignments", json={"student_ids": []}, headers=coord).status_code == 422
    client.post(f"/api/v1/paths/{pid}/status", json={"status": "published"}, headers=coord)
    ds = next(o for o in client.get("/api/v1/offerings", headers=coord).json() if o["course_code"] == "DS-201")
    target = (datetime.now(UTC) + timedelta(weeks=10)).isoformat()
    r = client.post(f"/api/v1/paths/{pid}/assignments", json={"cohort_offering_id": ds["id"], "target_date": target}, headers=coord)
    assert r.json() == {"created": 8, "skipped": 0}
    users = client.get("/api/v1/users?page_size=100", headers=coord).json()["items"]
    valeria = next(u for u in users if u["email"] == "estudiante@andino.demo")
    docente = next(u for u in users if u["email"] == "docente@andino.demo")
    assert client.post(f"/api/v1/paths/{pid}/assignments", json={"student_ids": [docente["id"]]}, headers=coord).status_code == 422
    assert client.post(f"/api/v1/paths/{pid}/assignments", json={"student_ids": [valeria["id"]]}, headers=coord).json()["created"] == 1

    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert any(n["kind"] == "path.assigned" for n in client.get("/api/v1/notifications", headers=est).json()["items"])
    mine = next(a for a in client.get("/api/v1/my/paths", headers=est).json() if a["path_title"] == "Ruta corta")
    assert mine["steps"][0]["status"] == "disponible" and mine["steps"][0]["available_offering_id"] == ds["id"]


def test_excepcion_autorizada_dispensa_la_etapa(client):
    coord = auth(client, "ANDINO", "coordinacion@andino.demo")
    path = _demo_path(client, coord)
    rows = client.get(f"/api/v1/paths/{path['id']}/assignments", headers=coord).json()
    valeria = next(r for r in rows if r["student_name"] == "Valeria Mendoza")
    step_py = path["steps"][0]["id"]
    r = client.post(f"/api/v1/path-assignments/{valeria['id']}/exceptions", headers=coord,
                    json={"step_id": step_py, "reason": "Convalidó Python con certificación externa"}).json()
    assert r["steps"][0]["status"] == "dispensado" and r["steps"][1]["status"] in ("disponible", "en_curso")
    assert r["completed_steps"] == 1
    assert client.post(f"/api/v1/path-assignments/{valeria['id']}/exceptions", headers=coord,
                       json={"step_id": step_py, "reason": "Duplicada otra vez sin motivo"}).status_code == 409


def test_permisos_de_rutas(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get("/api/v1/paths", headers=est).status_code == 403
    doc = auth(client, "ANDINO", "docente@andino.demo")
    path = _demo_path(client, doc)  # el docente consulta
    assert client.post("/api/v1/paths", headers=doc, json={"code": "X1", "title": "No", "objective": "No debería crear rutas.",
                                                          "steps": [{"course_id": path["steps"][0]["course_id"]}]}).status_code == 403
    analista = auth(client, "ANDINO", "analista@andino.demo")
    assert client.get(f"/api/v1/paths/{path['id']}/assignments", headers=analista).status_code == 403
    pac = auth(client, "PACIFICO", "admin@pacifico.demo")
    assert all(p["code"] != "RUTA-DATOS" for p in client.get("/api/v1/paths", headers=pac).json())
    other = client.get("/api/v1/my/paths", headers=auth(client, "ANDINO", "estudiante2@andino.demo")).json()[0]
    assert client.get(f"/api/v1/path-assignments/{other['id']}", headers=est).status_code == 404
