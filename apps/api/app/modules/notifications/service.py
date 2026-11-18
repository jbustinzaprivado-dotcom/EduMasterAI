"""Notificaciones y entrega en tiempo real (§4.12, §10.3, decisión D28).

1. `notify()` guarda la notificación en la MISMA transacción que la acción que la origina (como un Outbox).
2. Solo si la transacción se confirma, el evento se publica al broker en memoria (after_commit): nunca se
   anuncia algo que luego se deshizo.
3. El broker entrega por Server-Sent Events SOLO a las conexiones del usuario destinatario (§10.4: no hay
   canal global). Si el navegador estaba desconectado, al reconectar pide lo que se perdió (tabla en la base).
Una sola instancia de la API basta para la demo; con varias, el broker se reemplaza por Redis Streams (D11).
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections import defaultdict

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification

_PENDING_KEY = "pending_notifications"


class Broker:
    """Suscripciones por usuario: cada conexión SSE tiene su cola asyncio."""

    def __init__(self) -> None:
        self._subs: dict[uuid.UUID, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = defaultdict(set)
        self._lock = threading.Lock()

    def subscribe(self, user_id: uuid.UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subs[user_id].add((asyncio.get_running_loop(), queue))
        return queue

    def unsubscribe(self, user_id: uuid.UUID, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subs[user_id] = {s for s in self._subs[user_id] if s[1] is not queue}
            if not self._subs[user_id]:
                del self._subs[user_id]

    def connections(self, user_id: uuid.UUID | None = None) -> int:
        with self._lock:
            return len(self._subs.get(user_id, ())) if user_id else sum(len(s) for s in self._subs.values())

    def publish(self, user_id: uuid.UUID, payload: dict) -> None:
        """Seguro de llamar desde hilos (los endpoints síncronos corren en un pool de hilos)."""
        with self._lock:
            targets = list(self._subs.get(user_id, ()))
        for loop, queue in targets:
            def _put(q=queue, p=payload):
                if not q.full():  # un cliente lento no bloquea a los demás
                    q.put_nowait(p)
            loop.call_soon_threadsafe(_put)


broker = Broker()


def serialize(n: Notification) -> dict:
    return {
        "id": str(n.id), "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
        "created_at": n.created_at.isoformat(), "read_at": n.read_at.isoformat() if n.read_at else None,
    }


def notify(db: Session, user_ids, *, organization_id: uuid.UUID, kind: str, title: str, body: str = "",
           link: str | None = None) -> None:
    """Crea una notificación por destinatario. Se publica en vivo al confirmar la transacción."""
    for user_id in dict.fromkeys(user_ids):  # sin duplicados, en orden
        n = Notification(id=uuid.uuid4(), organization_id=organization_id, user_id=user_id, kind=kind,
                         title=title[:160], body=body, link=link)
        db.add(n)
        db.info.setdefault(_PENDING_KEY, []).append(n)


@event.listens_for(Session, "after_commit")
def _publish_after_commit(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, [])
    for n in pending:
        broker.publish(n.user_id, serialize(n))


@event.listens_for(Session, "after_rollback")
def _discard_on_rollback(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)
