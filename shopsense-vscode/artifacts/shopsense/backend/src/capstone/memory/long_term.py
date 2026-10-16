"""Minimal JSON-backed entity-scoped memory for local development."""

import json
import os
import re
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any


class EntityMemoryStore:
    """Persist notes under a stable opaque entity key, not a raw filesystem path."""

    def __init__(self, path: str | Path = "runtime/memory/entities.json"):
        self.path = Path(path)
        self._lock = RLock()

    @staticmethod
    def _key(entity_id: str) -> str:
        if not entity_id or not entity_id.strip():
            raise ValueError("entity_id is required")
        import hashlib
        return hashlib.sha256(entity_id.strip().casefold().encode("utf-8")).hexdigest()

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, entity_id: str) -> list[dict[str, Any]]:
        key = self._key(entity_id)
        with self._lock:
            return list(self._read().get(key, []))

    def add(self, entity_id: str, note: str, *, source: str = "application") -> None:
        if not note or not note.strip():
            raise ValueError("note is required")
        key = self._key(entity_id)
        with self._lock:
            data = self._read()
            notes = list(data.get(key, []))
            notes.append({"note": note.strip(), "source": source})
            data[key] = notes[-100:]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix="memory-", dir=str(self.path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(data, stream, indent=2, ensure_ascii=False)
                os.replace(temp_name, self.path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
