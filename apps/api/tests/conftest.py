"""Pruebas de la API. Por defecto usan SQLite en memoria; la CI define EDUMASTER_TEST_DATABASE_URL
para repetirlas contra PostgreSQL (decisión D13)."""

import os

os.environ["EDUMASTER_DATABASE_URL"] = os.environ.get("EDUMASTER_TEST_DATABASE_URL", "sqlite://")
os.environ["EDUMASTER_ENVIRONMENT"] = "test"
os.environ["EDUMASTER_PASSWORD_ITERATIONS"] = "1000"  # rápido; producción usa 600 000
os.environ["EDUMASTER_LOG_FORMAT"] = "text"
os.environ["EDUMASTER_WEB_DIST"] = "no-existe"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.rate_limit import login_limiter  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import run as seed  # noqa: E402

DEMO_PASSWORD = "ClaveDePrueba-2026"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db, DEMO_PASSWORD)
    login_limiter.reset()
    with TestClient(app) as c:
        yield c


def login(client: TestClient, org: str, email: str, password: str = DEMO_PASSWORD):
    return client.post("/api/v1/auth/login", json={"organization_code": org, "email": email, "password": password})


def auth(client: TestClient, org: str, email: str) -> dict:
    response = login(client, org, email)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
