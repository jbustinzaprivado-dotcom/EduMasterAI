"""IA en producto (§9.6-§9.8): aprobación humana, predicción por institución, permisos y revisión de alertas."""

from tests.conftest import auth


def _offering(client, headers, code):
    return next(o for o in client.get("/api/v1/offerings", headers=headers).json() if o["course_code"] == code)


def _approve(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    model = client.get("/api/v1/ml/models", headers=admin).json()[0]
    r = client.post(f"/api/v1/ml/models/{model['id']}/approve", json={"note": "Revisada la model card"}, headers=admin)
    assert r.status_code == 200 and r.json()["published_here"] is True
    return admin, model


def test_sin_aprobacion_no_hay_predicciones(client):
    ml = auth(client, "ANDINO", "ml@andino.demo")
    models = client.get("/api/v1/ml/models", headers=ml).json()
    assert models and models[0]["card"]["dataset"]["version"].startswith("v1")
    assert all(not m["published_here"] for m in models)
    arch = client.get("/api/v1/ml/architecture", headers=ml).json()
    assert arch["status"] == "design" and arch["version"] is None
    r = client.post("/api/v1/ml/predictions/run", json={}, headers=ml)
    assert r.status_code == 409 and r.json()["code"] == "no_model"
    # El ML Engineer registra y ejecuta, pero no aprueba la publicación (§3).
    assert client.post(f"/api/v1/ml/models/{models[0]['id']}/approve", json={}, headers=ml).status_code == 403


def test_aprobar_predecir_y_explicar(client):
    _approve(client)
    ml = auth(client, "ANDINO", "ml@andino.demo")
    run = client.post("/api/v1/ml/predictions/run", json={}, headers=ml).json()
    assert run["predictions"] > 0 and run["high_risk"] >= 1

    doc = auth(client, "ANDINO", "docente@andino.demo")
    py = _offering(client, doc, "PY-101")
    roster = {r["student_id"]: r for r in client.get(f"/api/v1/offerings/{py['id']}/enrollments", headers=doc).json()}
    risk = client.get(f"/api/v1/ml/offerings/{py['id']}/risk", headers=doc).json()
    valeria = next(r for r in risk if roster[r["student_id"]]["student_email"] == "estudiante@andino.demo")
    assert valeria["risk_level"] == "alto" and 0 <= valeria["score"] <= 1
    assert valeria["factors"] and all("label" in f and f["impact"] > 0 for f in valeria["factors"])
    # Quien completó el curso no recibe alerta.
    completed = {sid for sid, r in roster.items() if r["status"] == "completed"}
    assert completed and not completed & {r["student_id"] for r in risk}

    arch = client.get("/api/v1/ml/architecture", headers=doc).json()
    assert arch["status"] == "inference" and arch["version"] == "1.0.0" and arch["metrics"]["roc_auc"] > 0.5


def test_quien_ve_el_riesgo(client):
    _approve(client)
    doc = auth(client, "ANDINO", "docente@andino.demo")
    py = _offering(client, doc, "PY-101")
    client.post("/api/v1/ml/predictions/run", json={"offering_id": py["id"]}, headers=doc)  # docente: su oferta
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")
    assert client.get(f"/api/v1/ml/offerings/{py['id']}/risk", headers=doc2).status_code == 404
    assert client.post("/api/v1/ml/predictions/run", json={"offering_id": py["id"]}, headers=doc2).status_code == 404
    assert client.post("/api/v1/ml/predictions/run", json={}, headers=doc).status_code == 403  # toda la institución: no
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    assert client.get(f"/api/v1/ml/offerings/{py['id']}/risk", headers=est).status_code == 403  # D22
    analista = auth(client, "ANDINO", "analista@andino.demo")
    assert client.get(f"/api/v1/ml/offerings/{py['id']}/risk", headers=analista).status_code == 403


def test_la_aprobacion_es_por_institucion(client):
    _approve(client)
    pac = auth(client, "PACIFICO", "admin@pacifico.demo")
    assert client.get("/api/v1/ml/architecture", headers=pac).json()["status"] == "design"
    assert all(not m["published_here"] for m in client.get("/api/v1/ml/models", headers=pac).json())


def test_revision_humana_de_alertas(client):
    admin, _ = _approve(client)
    doc = auth(client, "ANDINO", "docente@andino.demo")
    py = _offering(client, doc, "PY-101")
    client.post("/api/v1/ml/predictions/run", json={"offering_id": py["id"]}, headers=doc)
    before = {k["key"]: k["value"] for k in client.get("/api/v1/dashboard/summary", headers=doc).json()["kpis"]}
    alert = next(r for r in client.get(f"/api/v1/ml/offerings/{py['id']}/risk", headers=doc).json() if r["risk_level"] == "alto")

    url = f"/api/v1/ml/predictions/{alert['prediction_id']}/review"
    assert client.patch(url, json={"status": "descartada"}, headers=doc).status_code == 422  # pide motivo
    r = client.patch(url, json={"status": "atendida", "note": "Se le escribió y respondió"}, headers=doc)
    assert r.status_code == 200 and r.json()["review_status"] == "atendida"
    after = {k["key"]: k["value"] for k in client.get("/api/v1/dashboard/summary", headers=doc).json()["kpis"]}
    assert after["risk_alerts"] == before["risk_alerts"] - 1
    logs = client.get("/api/v1/audit-logs?action=prediction.reviewed", headers=admin).json()["items"]
    assert logs[0]["details"]["status"] == "atendida"


def test_retirar_modelo_es_la_vuelta_atras(client):
    admin, model = _approve(client)
    ml = auth(client, "ANDINO", "ml@andino.demo")
    assert client.post("/api/v1/ml/predictions/run", json={}, headers=ml).status_code == 200
    url = f"/api/v1/ml/models/{model['id']}/retire"
    assert client.post(url, json={"reason": "x"}, headers=admin).status_code == 422  # motivo obligatorio
    assert client.post(url, json={"reason": "Prueba de rollback"}, headers=ml).status_code == 403  # solo quien aprueba
    r = client.post(url, json={"reason": "Prueba de rollback"}, headers=admin)
    assert r.status_code == 200 and r.json()["published_here"] is False
    assert client.post(url, json={"reason": "Prueba de rollback"}, headers=admin).status_code == 409
    # Sin modelo publicado no hay predicciones nuevas; el visualizador vuelve a "diseño".
    assert client.post("/api/v1/ml/predictions/run", json={}, headers=ml).json()["code"] == "no_model"
    assert client.get("/api/v1/ml/architecture", headers=ml).json()["status"] == "design"
    logs = client.get("/api/v1/audit-logs?action=model.retired", headers=admin).json()["items"]
    assert logs and logs[0]["details"]["reason"] == "Prueba de rollback"
    # Se puede volver a publicar la misma versión.
    assert client.post(f"/api/v1/ml/models/{model['id']}/approve", json={}, headers=admin).status_code == 200


def _valeria(client, doc):
    py = _offering(client, doc, "PY-101")
    roster = client.get(f"/api/v1/offerings/{py['id']}/enrollments", headers=doc).json()
    return py, next(r for r in roster if r["student_email"] == "estudiante@andino.demo")


def test_recorrido_real_de_una_prediccion(client):
    """D51: la traza usa las activaciones reales y su probabilidad coincide con la del modelo publicado."""
    doc = auth(client, "ANDINO", "docente@andino.demo")
    py, valeria = _valeria(client, doc)
    url = f"/api/v1/ml/enrollments/{valeria['enrollment_id']}/trace"
    r = client.get(url, headers=doc)
    assert r.status_code == 409 and r.json()["code"] == "no_model"  # sin aprobación no hay traza

    _approve(client)
    client.post("/api/v1/ml/predictions/run", json={"offering_id": py["id"]}, headers=doc)
    alert = next(a for a in client.get(f"/api/v1/ml/offerings/{py['id']}/risk", headers=doc).json()
                 if a["enrollment_id"] == valeria["enrollment_id"])
    t = client.get(url, headers=doc).json()
    assert abs(t["probability"] - alert["score"]) < 1e-3 and t["risk_level"] == alert["risk_level"] == "alto"
    assert [layer["id"] for layer in t["layers"]] == ["input", "projection", "temporal", "fusion", "heads"]
    assert [len(layer["nodes"]) for layer in t["layers"]] == [8, 6, 6, 5, 4]
    heads = t["layers"][-1]["nodes"]
    assert heads[2]["value"] == t["probability"] and all(h["value"] is None for i, h in enumerate(heads) if i != 2)
    ids = {layer["id"]: {n["index"] for n in layer["nodes"]} for layer in t["layers"]}
    assert t["edges"] and all(e["source"] in ids[e["source_layer"]] and e["target"] in ids[e["target_layer"]]
                              and 0 <= e["strength"] <= 1 for e in t["edges"])
    # Solo conexiones que existen en la red: la secuencia entra al bloque temporal, no a la rama tabular.
    pairs = {(e["source_layer"], e["target_layer"]) for e in t["edges"]}
    assert pairs == {("input", "projection"), ("input", "temporal"), ("projection", "fusion"),
                     ("temporal", "fusion"), ("fusion", "heads")}
    admin = auth(client, "ANDINO", "admin@andino.demo")
    audit = client.get("/api/v1/audit-logs?action=prediction.traced", headers=admin).json()
    assert any(e["resource_id"] == valeria["enrollment_id"] for e in audit["items"])


def test_quien_ve_el_recorrido(client):
    _approve(client)
    doc = auth(client, "ANDINO", "docente@andino.demo")
    _, valeria = _valeria(client, doc)
    url = f"/api/v1/ml/enrollments/{valeria['enrollment_id']}/trace"
    assert client.get(url, headers=auth(client, "ANDINO", "auditoria@andino.demo")).status_code == 200
    assert client.get(url, headers=auth(client, "ANDINO", "estudiante@andino.demo")).status_code == 403  # D22
    assert client.get(url, headers=auth(client, "ANDINO", "analista@andino.demo")).status_code == 403
    assert client.get(url, headers=auth(client, "ANDINO", "docente2@andino.demo")).status_code == 404
    assert client.get(url, headers=auth(client, "PACIFICO", "admin@pacifico.demo")).status_code == 404


def test_recorrido_del_grupo(client):
    """D52: la traza del grupo promedia a todas las matrículas activas y cuenta los niveles de riesgo."""
    _approve(client)
    doc = auth(client, "ANDINO", "docente@andino.demo")
    py, valeria = _valeria(client, doc)
    roster = client.get(f"/api/v1/offerings/{py['id']}/enrollments", headers=doc).json()
    active = [r for r in roster if r["status"] == "active"]
    client.post("/api/v1/ml/predictions/run", json={"offering_id": py["id"]}, headers=doc)
    risk = client.get(f"/api/v1/ml/offerings/{py['id']}/risk", headers=doc).json()

    g = client.get(f"/api/v1/ml/offerings/{py['id']}/trace", headers=doc).json()
    assert g["scope"] == "group" and g["enrollment_id"] is None and g["count"] == len(active)
    assert sum(g["levels"].values()) == len(active) and g["levels"]["alto"] >= 1 and g["factors"] == []
    mean = sum(r["score"] for r in risk) / len(risk)
    assert abs(g["probability"] - mean) < 1e-3  # la salida es el promedio real del grupo
    assert [len(layer["nodes"]) for layer in g["layers"]] == [8, 6, 6, 5, 4]

    one = client.get(f"/api/v1/ml/enrollments/{valeria['enrollment_id']}/trace", headers=doc).json()
    assert one["scope"] == "student" and one["count"] == 1 and sum(one["levels"].values()) == 1

    url = f"/api/v1/ml/offerings/{py['id']}/trace"
    assert client.get(url, headers=auth(client, "ANDINO", "estudiante@andino.demo")).status_code == 403
    assert client.get(url, headers=auth(client, "ANDINO", "docente2@andino.demo")).status_code == 404
