"""Datos DEMO de regiones y comunidad (decisión D06). Idempotente."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic.models import Course, CourseOffering
from app.modules.community.models import Comment, Post
from app.modules.identity.models import Organization, User

# Región por correo. Junín queda con 2 estudiantes a propósito: el mapa debe ocultarla (k = 3).
REGION_PLAN = {
    "ANDINO": ["Lima"] * 5 + ["Arequipa"] * 3 + ["Cusco"] * 3 + ["Junín"] * 2,
    "PACIFICO": ["Piura"],
}


def seed_regions(db: Session) -> None:
    for org_code, plan in REGION_PLAN.items():
        org = db.scalar(select(Organization).where(Organization.code == org_code))
        students = [u for u in db.scalars(select(User).where(User.organization_id == org.id).order_by(User.email))
                    if "estudiante" in u.role_codes]
        for user, region in zip(students, plan):
            user.region = user.region or region
    db.commit()


def seed_posts(db: Session, now: datetime | None = None) -> None:
    if db.scalar(select(Post.id).limit(1)):
        return
    now = now or datetime.now(UTC)
    users = {u.email: u for u in db.scalars(select(User))}
    offering = db.scalar(select(CourseOffering).join(Course).where(Course.code == "PY-101"))
    if offering is None:
        return

    def post(author, kind, title, body, days_ago):
        p = Post(organization_id=offering.organization_id, offering_id=offering.id, author_id=users[author].id,
                 kind=kind, title=title, body=body, created_at=now - timedelta(days=days_ago))
        db.add(p)
        db.flush()
        return p

    def comment(p, author, body, days_ago):
        db.add(Comment(post_id=p.id, author_id=users[author].id, body=body, created_at=now - timedelta(days=days_ago)))

    post("docente@andino.demo", "anuncio", "Examen final: indicaciones",
         "El examen final cubre las tres unidades. Revisen las prácticas y traigan sus dudas a la sesión de repaso. "
         "Recuerden que la entrega se hace en Evaluaciones antes de la fecha límite.", 2)
    debate = post("estudiante3@andino.demo", "debate", "¿Cómo practicar bucles sin aburrirse?",
                  "Me cuesta practicar for y while. ¿Qué ejercicios les funcionaron?", 9)
    comment(debate, "estudiante5@andino.demo", "A mí me sirvió hacer el juego de adivinar el número con límite de intentos.", 8)
    comment(debate, "docente@andino.demo", "Buena idea. Prueben también recorrer una lista de notas y calcular el promedio.", 8)
    post("estudiante7@andino.demo", "debate", "Grupo de estudio los jueves",
         "¿Alguien se suma a repasar funciones los jueves por la tarde?", 4)
    db.commit()


def run(db: Session) -> None:
    seed_regions(db)
    seed_posts(db)
