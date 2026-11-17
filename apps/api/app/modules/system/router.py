"""Health checks (§12): vivo (liveness) y listo (readiness, comprueba la base de datos)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DB
from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["sistema"])


@router.get("")
def live() -> dict:
    return {"status": "ok", "environment": get_settings().environment}


@router.get("/ready")
def ready(db: DB):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable", "database": "error"}, status_code=503)
    return {"status": "ok", "database": "ok"}
