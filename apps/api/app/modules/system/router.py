"""Health checks (§12) y métricas operativas (§12.1, D41)."""

from datetime import timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from app.api.deps import DB, require
from app.core.config import get_settings
from app.core.metrics import metrics
from app.db.base import utcnow
from app.modules.academic.models import LearningEvent
from app.modules.ml.models import Prediction
from app.modules.notifications.service import broker

router = APIRouter(prefix="/health", tags=["sistema"])
ops_router = APIRouter(prefix="/system", tags=["sistema"])


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


# Objetivos iniciales de §10.5 para comparar en la pantalla de operación.
TARGETS = {"api_read_p95_ms": 500, "dashboard_p95_ms": 2500, "inference_p95_ms": 800, "error_rate_5xx": 0.01}


@ops_router.get("/metrics", dependencies=[require("ops.read")])
def ops_metrics(db: DB) -> dict:
    """Métricas de la plataforma (no contienen datos personales) más frescura y uso del modelo."""
    snap = metrics.snapshot()
    last_event = db.scalar(select(func.max(LearningEvent.received_at)))
    since = utcnow() - timedelta(days=7)
    preds = db.execute(
        select(Prediction.risk_level, func.count()).where(Prediction.created_at >= since).group_by(Prediction.risk_level)
    ).all()
    return {
        **snap,
        "targets": TARGETS,
        "realtime": {"sse_connections": broker.connections(), "users_online": len(broker.online_user_ids())},
        "freshness": {"last_learning_event_at": last_event.isoformat() if last_event else None},
        "predictions_7d": {level: n for level, n in preds},
        "environment": get_settings().environment,
    }
