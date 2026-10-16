"""Thread-safe in-memory conversational context, isolated by session ID."""

from collections import defaultdict, deque
from threading import RLock
from typing import Any


class SessionMemory:
    def __init__(self, max_messages: int = 20):
        if max_messages < 1:
            raise ValueError("max_messages must be at least 1")
        self.max_messages = max_messages
        self._sessions: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.max_messages)
        )
        self._lock = RLock()

    def append(self, session_id: str, role: str, content: str) -> None:
        if not session_id or not session_id.strip():
            raise ValueError("session_id is required")
        if role not in {"user", "assistant", "system", "tool"}:
            raise ValueError("unsupported message role")
        with self._lock:
            self._sessions[session_id].append({"role": role, "content": content})

    def get(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
