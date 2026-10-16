"""Dependency-free tracing hook for local request spans.

A production deployment can provide a callback that exports these events to
LangFuse or another tracing backend; this module does not send network traffic.
"""

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Callable, Iterator


@contextmanager
def trace_span(
    name: str,
    *,
    trace_id: str | None = None,
    callback: Callable[[dict[str, Any]], None] | None = None,
) -> Iterator[dict[str, Any]]:
    event: dict[str, Any] = {"name": name, "trace_id": trace_id, "status": "running"}
    started = perf_counter()
    try:
        yield event
    except Exception as exc:
        event["status"] = "error"
        event["error_type"] = type(exc).__name__
        raise
    else:
        event["status"] = "ok"
    finally:
        event["duration_ms"] = round((perf_counter() - started) * 1000, 3)
        if callback:
            callback(dict(event))
