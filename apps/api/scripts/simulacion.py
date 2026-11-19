"""Simulación de un día de clases real contra una instalación en marcha (Fase 8, uso en entorno real).

Hace lo que harían las personas, con sus propios permisos y por la API pública (igual que la web):
  1. 13 estudiantes entran, abren sus cursos, avanzan actividades (eventos idempotentes), consultan al IA Tutor,
     valoran una sugerencia y algunos entregan evaluaciones pendientes.
  2. En la comunidad de un curso, una estudiante abre un debate y otra responde.
  3. El docente califica las entregas pendientes, actualiza el riesgo con IA y atiende la primera alerta alta.
  4. Controles que deben FALLAR: otra institución (404), estudiante en analítica (403), sin sesión (401).
  5. Verificación pública de un certificado, sin sesión.
Al final compara los indicadores de la institución antes y después, y lista cualquier respuesta inesperada.

Uso (desde apps/api, con la API en marcha):  python scripts/simulacion.py --url http://127.0.0.1:8000
La contraseña DEMO se lee de .env. ATENCIÓN: escribe datos en la base (haz `respaldo.bat` antes de una exposición).
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API = "/api/v1"
log: list[str] = []
problems: list[str] = []
counters: dict[str, int] = {}


def count(key: str, n: int = 1) -> None:
    counters[key] = counters.get(key, 0) + n


def expect(r: httpx.Response, ok: tuple[int, ...], what: str) -> httpx.Response:
    if r.status_code not in ok:
        detail = r.json().get("message") if r.headers.get("content-type", "").startswith("application/json") else r.text[:80]
        problems.append(f"{what}: HTTP {r.status_code} ({detail})")
    return r


def login(c: httpx.Client, org: str, email: str, password: str) -> dict:
    r = expect(c.post(f"{API}/auth/login", json={"organization_code": org, "email": email, "password": password}),
               (200,), f"login {email}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else {}


def kpis(c: httpx.Client, h: dict) -> dict[str, float]:
    return {k["key"]: k["value"] for k in c.get(f"{API}/dashboard/summary", headers=h).json()["kpis"]}


def student_day(c: httpx.Client, email: str, password: str, rnd: random.Random) -> None:
    h = login(c, "ANDINO", email, password)
    if not h:
        return
    count("estudiantes que entraron")
    for o in c.get(f"{API}/offerings", headers=h).json():
        detail = expect(c.get(f"{API}/offerings/{o['id']}", headers=h), (200,), f"{email} abre {o['course_code']}").json()
        mine = detail.get("my_enrollment")
        if not mine or mine["status"] != "active":
            continue
        done = set(mine["completed_activity_ids"])
        pending = [a for u in detail.get("units") or [] for a in u["activities"] if a["id"] not in done]
        session = {"event_id": str(uuid.uuid4()), "offering_id": o["id"], "event_type": "session_started"}
        expect(c.post(f"{API}/learning-events", json=session, headers=h), (200,), "evento de sesión")
        # Reenviar el mismo evento (p. ej. por mala red) no debe duplicarlo.
        again = expect(c.post(f"{API}/learning-events", json=session, headers=h), (200,), "evento repetido")
        if again.status_code == 200 and not again.json()["duplicate"]:
            problems.append("Un evento repetido no se marcó como duplicado (idempotencia).")
        count("eventos repetidos rechazados como duplicados")
        for a in pending[: rnd.choice([0, 1, 1, 2])]:  # algunos no avanzan hoy
            for kind, secs in (("activity_started", 0), ("activity_completed", a["estimated_minutes"] * 60)):
                r = expect(c.post(f"{API}/learning-events", headers=h, json={
                    "event_id": str(uuid.uuid4()), "offering_id": o["id"], "activity_id": a["id"],
                    "event_type": kind, "occurred_at": datetime.now(UTC).isoformat(), "duration_seconds": secs}),
                    (200,), f"{email} completa actividad")
            count("actividades completadas")
            if r.status_code == 200 and r.json()["enrollment_status"] == "completed":
                count("cursos terminados hoy")
        recs = expect(c.get(f"{API}/recommendations?offering_id={o['id']}", headers=h), (200,), "IA Tutor").json()
        count("consultas al IA Tutor")
        if recs and rnd.random() < 0.6:
            action = rnd.choice(["aceptar", "util", "no_util"])
            expect(c.post(f"{API}/recommendations/{recs[0]['id']}/feedback", json={"action": action}, headers=h),
                   (200,), "feedback de recomendación")
            count("valoraciones de sugerencias")
    for a in c.get(f"{API}/assessments", headers=h).json():
        mine = a.get("mine") or {}
        if mine.get("attempts", 0) == 0 and rnd.random() < 0.5:
            r = expect(c.post(f"{API}/assessments/{a['id']}/submissions", headers=h,
                              json={"answer": f"Entrega de la simulación ({email})."}), (200, 201, 422), "entrega")
            if r.status_code in (200, 201):
                count("entregas")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--password")
    ap.add_argument("--semilla", type=int, default=19)
    args = ap.parse_args()
    password = args.password
    if not password:
        from app.core.config import get_settings

        password = get_settings().demo_password
    rnd = random.Random(args.semilla)

    with httpx.Client(base_url=args.url.rstrip("/"), timeout=30) as c:
        admin = login(c, "ANDINO", "admin@andino.demo", password)
        before = kpis(c, admin)

        # 1. Estudiantes
        students = ["estudiante@andino.demo"] + [f"estudiante{i}@andino.demo" for i in range(2, 14)]
        for email in students:
            student_day(c, email, password, rnd)

        # 2. Comunidad
        est = login(c, "ANDINO", "estudiante@andino.demo", password)
        est2 = login(c, "ANDINO", "estudiante2@andino.demo", password)
        py = next((o for o in c.get(f"{API}/offerings", headers=est).json() if o["course_code"] == "PY-101"), None)
        if py:
            post = expect(c.post(f"{API}/offerings/{py['id']}/community/posts", headers=est, json={
                "kind": "debate", "title": "¿Listas o tuplas para guardar notas?",
                "body": "Para el ejercicio 3, ¿conviene usar una lista o una tupla? ¿Por qué?"}), (201,), "crear debate")
            if post.status_code == 201:
                count("debates")
                expect(c.post(f"{API}/community/posts/{post.json()['id']}/comments", headers=est2,
                              json={"body": "Lista, porque las notas cambian; la tupla no se puede modificar."}),
                       (201,), "responder debate")
                count("respuestas")

        # 3. Docente
        doc = login(c, "ANDINO", "docente@andino.demo", password)
        for a in c.get(f"{API}/assessments", headers=doc).json():
            for t in expect(c.get(f"{API}/assessments/{a['id']}/attempts", headers=doc), (200,), "ver entregas").json():
                if t["score"] is None:
                    score = rnd.choice([11, 13, 14, 15, 16, 17, 18])
                    expect(c.patch(f"{API}/attempts/{t['id']}", headers=doc, json={
                        "score": min(score, a["max_score"]), "feedback": "Bien resuelto; revisa los casos borde."}),
                        (200,), "calificar")
                    count("notas publicadas (aviso en vivo al estudiante)")
        alerts_reviewed = False
        for o in c.get(f"{API}/offerings", headers=doc).json():
            r = expect(c.post(f"{API}/ml/predictions/run", json={"offering_id": o["id"]}, headers=doc),
                       (200, 409), f"riesgo IA {o['course_code']}")
            if r.status_code == 200:
                count("predicciones de riesgo", r.json()["predictions"])
                count("riesgo alto", r.json()["high_risk"])
            rows = c.get(f"{API}/ml/offerings/{o['id']}/risk", headers=doc).json() if r.status_code == 200 else []
            high = [x for x in rows if x["risk_level"] == "alto" and x["review_status"] == "pendiente"]
            if high and not alerts_reviewed:
                expect(c.patch(f"{API}/ml/predictions/{high[0]['prediction_id']}/review", headers=doc, json={
                    "status": "atendida", "note": "Conversé con la estudiante; acordamos un plan de ponerse al día."}),
                    (200,), "atender alerta")
                count("alertas atendidas")
                alerts_reviewed = True

        # 4. Controles que deben fallar
        pac = login(c, "PACIFICO", "admin@pacifico.demo", password)
        andino_offering = c.get(f"{API}/offerings", headers=admin).json()[0]["id"]
        checks = [
            ("Otra institución abre una oferta de ANDINO", c.get(f"{API}/offerings/{andino_offering}", headers=pac), 404),
            ("Estudiante entra a la analítica", c.get(f"{API}/analytics/overview", headers=est), 403),
            ("Estudiante intenta calificar", c.patch(f"{API}/attempts/{uuid.uuid4()}", headers=est,
                                                      json={"score": 20}), 404),
            ("Sin sesión pide el panel", c.get(f"{API}/dashboard/summary"), 401),
            ("ML Engineer intenta aprobar su modelo", c.post(f"{API}/ml/models/{uuid.uuid4()}/approve", json={},
                                                           headers=login(c, "ANDINO", "ml@andino.demo", password)), 403),
        ]
        for what, r, code in checks:
            if r.status_code != code:
                problems.append(f"CONTROL FALLIDO · {what}: esperaba {code}, recibió {r.status_code}")
            log.append(f"[{'OK' if r.status_code == code else 'FALLO'}] {what} → {r.status_code} (esperado {code})")

        # 5. Verificación pública de un certificado
        certs = c.get(f"{API}/certificates", headers=admin).json()
        if certs:
            r = expect(c.get(f"{API}/certificates/verify/{certs[0]['verification_code']}"), (200,), "verificación pública")
            log.append(f"[{'OK' if r.status_code == 200 else 'FALLO'}] Verificación pública del folio {certs[0]['folio']} "
                       f"sin sesión → {r.status_code}")

        after = kpis(c, admin)

    print("=== Simulación de un día de clases ===")
    for k, v in counters.items():
        print(f"  {k}: {v}")
    print("\n=== Controles de seguridad ===")
    print("\n".join("  " + x for x in log))
    print("\n=== Indicadores de la institución (antes → después) ===")
    for k in after:
        if before.get(k) != after[k]:
            print(f"  {k}: {before.get(k)} → {after[k]}")
    print("\n=== Respuestas inesperadas ===")
    print("\n".join("  " + p for p in problems) if problems else "  ninguna")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
