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
