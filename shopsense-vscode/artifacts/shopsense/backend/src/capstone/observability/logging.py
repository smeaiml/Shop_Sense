"""Structured, redacted application logging helpers."""

import json
import logging
from typing import Any

SENSITIVE_KEY_PARTS = ("password", "secret", "token", "api_key", "authorization")


def redact_fields(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if any(part in str(key).casefold() for part in SENSITIVE_KEY_PARTS):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = redact_fields(item)
        return result
    if isinstance(value, list):
        return [redact_fields(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event_data = getattr(record, "event_data", None)
        if event_data is not None:
            payload["event_data"] = redact_fields(event_data)
        return json.dumps(payload, ensure_ascii=False, default=str)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(event, extra={"event_data": redact_fields(fields)})
