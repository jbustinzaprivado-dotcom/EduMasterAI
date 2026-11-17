"""Logs estructurados con correlation_id (§12)."""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.context import correlation_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        extra = getattr(record, "extra_data", None)
        if extra:
            data.update(extra)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<7} [{correlation_id.get()}] {record.name}: {record.getMessage()}"
        extra = getattr(record, "extra_data", None)
        return f"{base} {extra}" if extra else base


def configure_logging(fmt: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").disabled = True  # el middleware ya registra cada petición
