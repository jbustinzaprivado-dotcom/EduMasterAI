"""Centro de notificaciones y canal en vivo (§4.12, §10.3)."""

import asyncio
import json
import uuid
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select, update

from app.api.deps import DB, CurrentPrincipal
from app.core.database import SessionLocal
from app.core.errors import AppError, not_found
from app.core.security import decode_access_token
from app.modules.identity.models import User
from app.modules.notifications.models import Notification
from app.modules.notifications.service import broker, serialize

router = APIRouter(prefix="/notifications", tags=["notificaciones"])
HEARTBEAT_SECONDS = 15


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    link: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread: int


@router.get("", response_model=NotificationList)
def list_notifications(db: DB, principal: CurrentPrincipal, limit: int = Query(default=20, ge=1, le=100),
                       unread_only: bool = False) -> NotificationList:
    q = select(Notification).where(Notification.user_id == principal.user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    rows = db.scalars(q.order_by(Notification.created_at.desc()).limit(limit))
    unread = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == principal.user.id, Notification.read_at.is_(None))) or 0
    return NotificationList(items=[NotificationOut.model_validate(serialize(n)) for n in rows], unread=unread)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> NotificationOut:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != principal.user.id:
        raise not_found("Notificación")
    n.read_at = n.read_at or datetime.now(UTC)
    db.commit()
    return NotificationOut.model_validate(serialize(n))


@router.post("/read-all", status_code=204)
def mark_all_read(db: DB, principal: CurrentPrincipal) -> None:
    db.execute(update(Notification).where(Notification.user_id == principal.user.id, Notification.read_at.is_(None))
               .values(read_at=datetime.now(UTC)))
    db.commit()


def _authenticate(authorization: str | None) -> User:
    """Autenticación del canal en vivo: el token viaja en la cabecera (fetch), nunca en la URL."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "unauthorized", "Falta el token de acceso.")
    try:
        user_id = uuid.UUID(decode_access_token(authorization[7:])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AppError(401, "unauthorized", "Sesión no válida o expirada.") from None
    with SessionLocal() as db:  # se cierra antes de abrir el stream: no retiene conexiones a la base
        user = db.get(User, user_id)
        if user is None or user.status != "active":
            raise AppError(401, "unauthorized", "Sesión no válida o expirada.")
        db.expunge(user)
        return user


def _missed(user_id: uuid.UUID, last_event_id: str | None) -> list[dict]:
    """Notificaciones posteriores a la última recibida (reconexión, §13.1 criterio 26)."""
    if not last_event_id:
        return []
    with SessionLocal() as db:
        try:
            last = db.get(Notification, uuid.UUID(last_event_id))
        except ValueError:
            return []
        if last is None or last.user_id != user_id:
            return []
        rows = db.scalars(select(Notification).where(Notification.user_id == user_id,
                                                     Notification.created_at > last.created_at)
                          .order_by(Notification.created_at))
        return [serialize(n) for n in rows]


def _sse(payload: dict) -> str:
    return f"id: {payload['id']}\nevent: notification\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/stream")
async def stream(request: Request, authorization: str | None = Header(default=None),
                 last_event_id: str | None = Header(default=None)):
    """Server-Sent Events: notificaciones del usuario en vivo, con latido cada 15 s y recuperación al reconectar."""
    user = await asyncio.to_thread(_authenticate, authorization)
    missed = await asyncio.to_thread(_missed, user.id, last_event_id)
    queue = broker.subscribe(user.id)

    async def events():
        try:
            yield f"event: ready\ndata: {json.dumps({'user': str(user.id)})}\n\n"
            for payload in missed:
                yield _sse(payload)
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield _sse(payload)
                except TimeoutError:
                    yield ": latido\n\n"  # mantiene viva la conexión a través del túnel
        finally:
            broker.unsubscribe(user.id, queue)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)
