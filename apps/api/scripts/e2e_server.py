"""Servidor aislado para las pruebas E2E (§13): base SQLite nueva, datos DEMO y la web compilada.

Uso (lo lanza Playwright):  python scripts/e2e_server.py
No toca la base de desarrollo ni el .env: usa su propio archivo en data/e2e.db y una contraseña de prueba.
"""

import os
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
DB = ROOT / "data" / "e2e.db"
PORT = int(os.environ.get("E2E_PORT", "8010"))

os.environ.update({
    "EDUMASTER_DATABASE_URL": f"sqlite:///{DB.as_posix()}",
    "EDUMASTER_ENVIRONMENT": "development",
    "EDUMASTER_DEMO_PASSWORD": os.environ.get("E2E_PASSWORD", "ClaveE2E-2026"),
    "EDUMASTER_PASSWORD_ITERATIONS": "1000",
    "EDUMASTER_JWT_SECRET": "e2e-solo-pruebas-0123456789abcdefghijklmnop",
    "EDUMASTER_LOG_FORMAT": "text",
    "EDUMASTER_LOGIN_RATE_LIMIT": "1000",  # todas las pruebas entran desde 127.0.0.1
})
sys.path.insert(0, str(API))

DB.parent.mkdir(parents=True, exist_ok=True)
for suffix in ("", "-journal", "-wal", "-shm"):
    Path(str(DB) + suffix).unlink(missing_ok=True)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

cfg = Config(str(API / "alembic.ini"))
cfg.set_main_option("script_location", str(API / "migrations"))
command.upgrade(cfg, "head")  # las E2E también prueban que las migraciones crean un esquema usable

from app.core.database import SessionLocal  # noqa: E402
from app.seed import run as seed  # noqa: E402

with SessionLocal() as db:
    seed(db, os.environ["EDUMASTER_DEMO_PASSWORD"])

import uvicorn  # noqa: E402

uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")
