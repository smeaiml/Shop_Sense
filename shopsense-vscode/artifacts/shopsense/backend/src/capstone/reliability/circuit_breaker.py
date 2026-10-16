"""Small synchronous circuit breaker for unreliable external dependencies."""

from time import monotonic
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when a circuit is open and calls are rejected safely."""


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: float = 30.0):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if reset_timeout_seconds < 0:
            raise ValueError("reset_timeout_seconds must be non-negative")
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if monotonic() - self.opened_at >= self.reset_timeout_seconds:
            return False  # permit a trial call; success/failure closes or reopens
        return True

    def call(self, operation: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        if self.is_open:
            raise CircuitOpenError("Dependency circuit is open; use a safe fallback.")
        try:
            result = operation(*args, **kwargs)
        except Exception:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.opened_at = monotonic()
            raise
        self.failures = 0
        self.opened_at = None
        return result
