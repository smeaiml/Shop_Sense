"""Bounded retry helper for transient service failures."""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def call_with_retries(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    retryable_exceptions: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError),
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> T:
    """Retry only configured transient errors, with a strict attempt bound."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except retryable_exceptions as exc:
            if attempt >= max_attempts:
                raise
            if on_retry:
                on_retry(attempt, exc)
    raise RuntimeError("unreachable retry state")
