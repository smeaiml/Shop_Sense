"""Durable SQLite checkpointing for interrupt-and-resume support workflows."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from capstone.settings import DATABASE_PATH


def make_checkpointer(path: str | Path | None = None) -> Any:
    db_path = Path(path or DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=20, check_same_thread=False)
    connection.execute("PRAGMA busy_timeout=20000")
    connection.execute("PRAGMA journal_mode=WAL")
    saver = SqliteSaver(connection)
    saver.setup()
    return saver
