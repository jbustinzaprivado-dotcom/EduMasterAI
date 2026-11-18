"""Notificaciones en vivo (§4.12, §10.3) y certificados con verificación pública (§4.7)."""

import asyncio
import uuid

from app.core.database import SessionLocal
from app.modules.identity.models import User
from app.modules.notifications.router import _missed
from app.modules.notifications.service import broker, notify
from tests.conftest import auth


def _offering(client, headers, code):
    return next(o for o in client.get("/api/v1/offerings", headers=headers).json() if o["course_code"] == code)


# ---------- notificaciones ----------

def test_nota_publicada_notifica_al_estudiante(client):
    doc = auth(client, "ANDINO", "docente@andino.demo")
    est = auth(client, "ANDINO", "estudiante@andino.demo")
    final = next(a for a in client.get("/api/v1/assessments", headers=est).json() if a["title"] == "Examen final")
    client.post(f"/api/v1/assessments/{final['id']}/submissions", json={"answer": "Respuesta"}, headers=est)
    attempt = next(t for t in client.get(f"/api/v1/assessments/{final['id']}/attempts", headers=doc).json()
                   if t["student_name"] == "Valeria Mendoza")
    client.patch(f"/api/v1/attempts/{attempt['id']}", json={"score": 15}, headers=doc)

    data = client.get("/api/v1/notifications", headers=est).json()
    note = next(n for n in data["items"] if n["kind"] == "grade.recorded")
    assert "Examen final" in note["title"] and note["body"].startswith("15/20") and note["read_at"] is None
    assert data["unread"] >= 1
    # Nadie más puede marcarla.
    otro = auth(client, "ANDINO", "estudiante2@andino.demo")
    assert client.post(f"/api/v1/notifications/{note['id']}/read", headers=otro).status_code == 404
    assert client.post(f"/api/v1/notifications/{note['id']}/read", headers=est).json()["read_at"]
    client.post("/api/v1/notifications/read-all", headers=est)
    assert client.get("/api/v1/notifications", headers=est).json()["unread"] == 0


def test_alertas_de_riesgo_notifican_al_docente(client):
    admin = auth(client, "ANDINO", "admin@andino.demo")
    model = client.get("/api/v1/ml/models", headers=admin).json()[0]
    client.post(f"/api/v1/ml/models/{model['id']}/approve", json={}, headers=admin)
    ml = auth(client, "ANDINO", "ml@andino.demo")
    assert any(n["kind"] == "model.published" for n in client.get("/api/v1/notifications", headers=ml).json()["items"])
    client.post("/api/v1/ml/predictions/run", json={}, headers=ml)
    doc = auth(client, "ANDINO", "docente@andino.demo")
    alerts = [n for n in client.get("/api/v1/notifications", headers=doc).json()["items"] if n["kind"] == "risk.alerts"]
    assert alerts and "alerta" in alerts[0]["title"]
    # La notificación al docente no revela datos a otros docentes.
    doc2 = auth(client, "ANDINO", "docente2@andino.demo")
    assert all("Fundamentos de Python" not in n["title"] for n in client.get("/api/v1/notifications", headers=doc2).json()["items"])


def test_canal_en_vivo_requiere_token(client):
    assert client.get("/api/v1/notifications/stream").status_code == 401
    assert client.get("/api/v1/notifications/stream", headers={"Authorization": "Bearer x"}).status_code == 401


def test_broker_entrega_solo_al_destinatario_y_tras_confirmar(client):
    with SessionLocal() as db:
        users = {u.email: u for u in db.query(User).all()}
    valeria, ana = users["estudiante@andino.demo"], users["estudiante2@andino.demo"]

    async def scenario():
        q_val, q_ana = broker.subscribe(valeria.id), broker.subscribe(ana.id)

        def write(commit: bool):
            with SessionLocal() as db:
                notify(db, [valeria.id], organization_id=valeria.organization_id, kind="test", title="Hola")
                db.commit() if commit else db.rollback()

        await asyncio.to_thread(write, False)  # deshecha: no debe anunciarse
        await asyncio.to_thread(write, True)
        got = await asyncio.wait_for(q_val.get(), timeout=2)
        empty = q_ana.empty() and q_val.empty()
        broker.unsubscribe(valeria.id, q_val)
        broker.unsubscribe(ana.id, q_ana)
        return got, empty

    got, empty = asyncio.run(scenario())
    assert got["title"] == "Hola" and empty
    assert broker.connections() == 0


def test_reconexion_recupera_lo_perdido(client):
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == "docente@andino.demo").one()
        for i in range(3):
            notify(db, [u.id], organization_id=u.organization_id, kind="test", title=f"Aviso {i}")
            db.commit()
        from app.modules.notifications.models import Notification
        first = db.query(Notification).filter(Notification.user_id == u.id, Notification.title == "Aviso 0").one()
    missed = _missed(u.id, str(first.id))
    assert [m["title"] for m in missed][-2:] == ["Aviso 1", "Aviso 2"]
    assert _missed(u.id, str(uuid.uuid4())) == [] and _missed(u.id, "basura") == []


# ---------- certificados ----------

def _certified(client):
    doc = auth(client, "ANDINO", "docente@andino.demo")
    py = _offering(client, doc, "PY-101")
    rows = client.get(f"/api/v1/certificates/offerings/{py['id']}", headers=doc).json()
    return doc, py, rows


def test_emision_automatica_y_elegibilidad(client):
    doc, _, rows = _certified(client)
    issued = [r for r in rows if r["certificate"]]
    assert issued and all(r["eligible"] and r["final_grade"] >= 11 for r in issued)
    assert issued[0]["certificate"]["folio"].startswith("EDM-ANDINO-") and issued[0]["certificate"]["issued_by_system"]
    valeria = next(r for r in rows if r["student_name"] == "Valeria Mendoza")
    assert not valeria["eligible"] and "Avance" in valeria["reason"]
    r = client.post("/api/v1/certificates", json={"enrollment_id": valeria["enrollment_id"]}, headers=doc)
    assert r.status_code == 422 and r.json()["code"] == "not_eligible"
    r = client.post("/api/v1/certificates", json={"enrollment_id": issued[0]["enrollment_id"]}, headers=doc)
    assert r.status_code == 409  # sin duplicados vigentes


def test_verificacion_publica_con_datos_minimos(client):
    _, _, rows = _certified(client)
    cert = next(r["certificate"] for r in rows if r["certificate"])
    r = client.get(f"/api/v1/certificates/verify/{cert['verification_code'].lower()}")  # sin sesión
    body = r.json()
    assert r.status_code == 200 and body["valid"] is True and body["folio"] == cert["folio"]
    assert set(body) == {"valid", "status", "folio", "student_name", "course_title", "institution", "issued_at", "revoked_at"}
    assert client.get("/api/v1/certificates/verify/NOEXISTE00").status_code == 404


def test_pdf_solo_para_el_titular_o_su_docente(client):
    doc, _, rows = _certified(client)
    row = next(r for r in rows if r["certificate"])
    cert = row["certificate"]
    pdf = client.get(f"/api/v1/certificates/{cert['id']}/pdf", headers=doc)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    otro = auth(client, "ANDINO", "estudiante@andino.demo")  # Valeria no es la titular
    assert client.get(f"/api/v1/certificates/{cert['id']}/pdf", headers=otro).status_code == 404
    admin = auth(client, "ANDINO", "admin@andino.demo")
    logs = client.get("/api/v1/audit-logs?action=certificate.downloaded", headers=admin).json()["items"]
    assert logs[0]["details"]["folio"] == cert["folio"]


def test_anular_y_reemitir(client):
    doc, _, rows = _certified(client)
    row = next(r for r in rows if r["certificate"])
    cert = row["certificate"]
    assert client.post(f"/api/v1/certificates/{cert['id']}/revoke", json={"reason": "Error en datos"}, headers=doc).status_code == 403
    admin = auth(client, "ANDINO", "admin@andino.demo")
    r = client.post(f"/api/v1/certificates/{cert['id']}/revoke", json={"reason": "Error en el nombre"}, headers=admin)
    assert r.json()["status"] == "anulado"
    assert client.get(f"/api/v1/certificates/verify/{cert['verification_code']}").json()["valid"] is False
    new = client.post("/api/v1/certificates", json={"enrollment_id": row["enrollment_id"]}, headers=admin).json()
    assert new["status"] == "emitido" and new["folio"] != cert["folio"]
    pac = auth(client, "PACIFICO", "admin@pacifico.demo")
    assert client.post(f"/api/v1/certificates/{new['id']}/revoke", json={"reason": "Otra institución"}, headers=pac).status_code == 404


def test_completar_sin_notas_suficientes_no_emite(client):
    est = auth(client, "PACIFICO", "estudiante@pacifico.demo")
    atn = _offering(client, est, "ATN-100")
    detail = client.get(f"/api/v1/offerings/{atn['id']}", headers=est).json()
    for unit in detail["units"]:
        for activity in unit["activities"]:
            client.post("/api/v1/learning-events", headers=est, json={
                "event_id": str(uuid.uuid4()), "offering_id": atn["id"], "activity_id": activity["id"],
                "event_type": "activity_completed"})
    kinds = {n["kind"] for n in client.get("/api/v1/notifications", headers=est).json()["items"]}
    assert "course.completed" in kinds and "certificate.issued" not in kinds  # falta calificar el 50 % del peso
    assert client.get("/api/v1/certificates", headers=est).json() == []
