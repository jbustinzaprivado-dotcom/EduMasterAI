"""Carga las instituciones y cuentas DEMO (decisión D06: todo dato sintético va rotulado DEMO).

Uso (desde apps/api):  python -m app.seed
Requiere EDUMASTER_DEMO_PASSWORD en el .env: es la contraseña común de las cuentas DEMO.
Es idempotente: si una cuenta ya existe, no la toca.
"""

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.demo import academic, community, paths, skills
from app.modules.identity.models import Organization, User
from app.modules.identity.service import roles_by_code, sync_catalog

ORGANIZATIONS = [
    # (código, nombre, es plataforma)
    ("PLATAFORMA", "EduMaster.ai · Plataforma", True),
    ("ANDINO", "Instituto Andino de Tecnología (DEMO)", False),
    ("PACIFICO", "Centro de Capacitación Pacífico (DEMO)", False),
]

# (institución, correo, nombre, roles). Nombres ficticios.
ACCOUNTS = [
    ("PLATAFORMA", "superadmin@edumaster.demo", "Sofía Paredes", ["superadmin"]),
    ("ANDINO", "admin@andino.demo", "Martín Quispe", ["admin"]),
    ("ANDINO", "coordinacion@andino.demo", "Lucía Fernández", ["coordinador"]),
    ("ANDINO", "docente@andino.demo", "Jorge Huamán", ["docente"]),
    ("ANDINO", "docente2@andino.demo", "Patricia Rojas", ["docente"]),
    ("ANDINO", "estudiante@andino.demo", "Valeria Mendoza", ["estudiante"]),
    ("ANDINO", "analista@andino.demo", "Diego Salazar", ["analista"]),
    ("ANDINO", "ml@andino.demo", "Andrea Castillo", ["ml_engineer"]),
    ("ANDINO", "auditoria@andino.demo", "Ricardo Vega", ["auditor"]),
    ("PACIFICO", "admin@pacifico.demo", "Carmen Torres", ["admin"]),
    ("PACIFICO", "docente@pacifico.demo", "Luis Chávez", ["docente"]),
    ("PACIFICO", "estudiante@pacifico.demo", "Camila Ríos", ["estudiante"]),
]

_STUDENT_NAMES = [
    "Ana Flores", "Bruno Gutiérrez", "Carla Ramos", "Daniel Soto", "Elena Vargas", "Fernando Díaz",
    "Gabriela Cruz", "Héctor Medina", "Isabel Navarro", "Javier Ortiz", "Karen Silva", "Manuel Reyes",
]
ACCOUNTS += [
    ("ANDINO", f"estudiante{i + 2}@andino.demo", name, ["estudiante"]) for i, name in enumerate(_STUDENT_NAMES)
]


def run(db: Session, password: str) -> tuple[int, int, int]:
    sync_catalog(db)
    orgs = {o.code: o for o in db.scalars(select(Organization))}
    for code, name, is_platform in ORGANIZATIONS:
        if code not in orgs:
            orgs[code] = Organization(code=code, name=name, is_platform=is_platform)
            db.add(orgs[code])
    db.flush()

    created = 0
    password_hash = hash_password(password)  # mismo hash para todas: el seed tarda menos
    for org_code, email, full_name, roles in ACCOUNTS:
        org = orgs[org_code]
        exists = db.scalar(select(User).where(User.organization_id == org.id, User.email == email))
        if exists:
            continue
        db.add(User(organization_id=org.id, email=email, full_name=full_name,
                    password_hash=password_hash, roles=roles_by_code(db, roles)))
        created += 1
    db.commit()
    community.seed_regions(db)  # antes de la historia: el mapa usa la región de cada estudiante
    events = academic.run(db)  # cursos, ofertas, matrículas, evaluaciones e historia DEMO
    community.seed_posts(db)
    paths.run(db)
    skills.run(db)
    return len(orgs), created, events


def main() -> None:
    password = get_settings().demo_password
    if not password or len(password) < 10:
        sys.exit("Define EDUMASTER_DEMO_PASSWORD (mínimo 10 caracteres) en el archivo .env de la raíz.")
    with SessionLocal() as db:
        orgs, created, events = run(db, password)
    print(f"Instituciones: {orgs}. Cuentas DEMO nuevas: {created} (de {len(ACCOUNTS)}). "
          f"Eventos de aprendizaje DEMO nuevos: {events}.")


if __name__ == "__main__":
    main()
