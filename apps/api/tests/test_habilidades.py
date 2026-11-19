"""Dominio de habilidades (§4.9): catálogo, evidencias, heatmap, nivel estimado vs. validado y permisos."""

from tests.conftest import auth


def _user(client, headers, email):
    return next(u for u in client.get("/api/v1/users?page_size=100", headers=headers).json()["items"] if u["email"] == email)


def test_catalogo_jerarquico(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    skills = client.get("/api/v1/skills", headers=est).json()
    areas = [s for s in skills if s["parent_id"] is None]
    assert {a["code"] for a in areas} == {"PROG", "DATA", "ML"}
    py = next(s for s in skills if s["code"] == "PROG-PY")
    assert py["courses"] == ["PY-101"] and py["parent_id"] == next(a["id"] for a in areas if a["code"] == "PROG")
    assert client.get("/api/v1/skills", headers=auth(client, "PACIFICO", "admin@pacifico.demo")).json() == []


def test_heatmap_estimado_y_validado_por_separado(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    h = client.get("/api/v1/analytics/skill-mastery", headers=admin).json()
    assert h["levels"] == ["principiante", "elemental", "intermedio", "avanzado", "experto"] and h["engine"]
    rows = {r["code"]: r for r in h["rows"]}
    assert set(rows) == {"PROG-PY", "PROG-CTRL", "PROG-FUNC", "DATA-EXP", "DATA-LIMP", "DATA-AGG", "ML-FUND", "ML-SUP", "ML-EVAL"}
    assert sum(rows["PROG-PY"]["estimated"]) == 13 and sum(rows["PROG-PY"]["validated"]) == 0
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get("/api/v1/analytics/skill-mastery", headers=est).status_code == 403


def test_evidencias_del_estudiante_y_validacion_docente(client):
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    mine = {s["code"]: s for s in client.get("/api/v1/my/skills", headers=est).json()}
    py = mine["PROG-PY"]
    assert py["estimated_level"] and py["validated_level"] is None and py["evidences"]
    assert {e["source"] for e in py["evidences"]} <= {"unidad", "evaluacion"}
    assert 0 <= py["score"] < 1

    doc = auth(client, "ANDINO", "docente@andino.demo")
    valeria = _user(client, auth(client, "ANDINO", "admin@andino.demo"), "estudiante@andino.demo")
    body = {"student_id": valeria["id"], "skill_id": py["skill_id"], "level": 3, "note": "Resolvió bien la práctica en clase."}
    out = {s["code"]: s for s in client.post("/api/v1/skills/validations", json=body, headers=doc).json()}
    assert out["PROG-PY"]["validated_label"] == "intermedio" and out["PROG-PY"]["validated_by"] == "Jorge Huamán"
    assert out["PROG-PY"]["estimated_level"] == py["estimated_level"]  # el estimado no se pisa

    again = {s["code"]: s for s in client.get("/api/v1/my/skills", headers=est).json()}
    assert again["PROG-PY"]["validated_level"] == 3
    assert any(n["kind"] == "skill.validated" for n in client.get("/api/v1/notifications", headers=est).json()["items"])
    h = client.get("/api/v1/analytics/skill-mastery", headers=doc).json()
    assert next(r for r in h["rows"] if r["code"] == "PROG-PY")["validated"][2] == 1
    log = client.get("/api/v1/audit-logs?action=skill.validated", headers=auth(client, "ANDINO", "admin@andino.demo")).json()["items"][0]
    assert log["details"]["level"] == "intermedio"


def test_permisos_de_validacion(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    valeria = _user(client, admin, "estudiante@andino.demo")
    skills = {s["code"]: s for s in client.get("/api/v1/skills", headers=admin).json()}
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")  # no dicta a Valeria
    body = {"student_id": valeria["id"], "skill_id": skills["PROG-PY"]["id"], "level": 5, "note": "Intento sin ser su docente"}
    assert client.post("/api/v1/skills/validations", json=body, headers=doc2).status_code == 404
    assert client.get(f"/api/v1/skills/students/{valeria['id']}", headers=doc2).status_code == 404
    otro = auth(client, "ANDINO", "estudiante2@andino.demo")
    assert client.get(f"/api/v1/skills/students/{valeria['id']}", headers=otro).status_code == 404
    doc = auth(client, "ANDINO", "docente@andino.demo")  # dicta PY-101 pero no DS-201
    body["skill_id"] = skills["DATA-LIMP"]["id"]
    assert client.post("/api/v1/skills/validations", json=body, headers=doc).status_code == 422


def test_gestion_del_catalogo_y_vinculos(client):
    coord = auth(client, "ANDINO", "coordinacion@andino.demo")
    area = next(s for s in client.get("/api/v1/skills", headers=coord).json() if s["code"] == "PROG")
    new = client.post("/api/v1/skills", json={"code": "prog-test", "name": "Pruebas unitarias", "parent_id": area["id"]}, headers=coord)
    assert new.status_code == 201 and new.json()["code"] == "PROG-TEST"
    assert client.post("/api/v1/skills", json={"code": "x2", "name": "Nieta", "parent_id": new.json()["id"]}, headers=coord).status_code == 422
    courses = {c["code"]: c for c in client.get("/api/v1/courses", headers=coord).json()}
    r = client.put(f"/api/v1/courses/{courses['WEB-110']['id']}/skills", json=[{"skill_id": new.json()["id"]}], headers=coord)
    assert r.json() == {"course": "WEB-110", "skills": 1}
    assert client.put(f"/api/v1/courses/{courses['WEB-110']['id']}/skills", json=[{"skill_id": area["id"]}], headers=coord).status_code == 422
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.post("/api/v1/skills", json={"code": "NO", "name": "No permitido"}, headers=est).status_code == 403
