"""Explicit safe fallback responses for unavailable dependencies."""

from typing import Any


def safe_fallback(
    message: str = "The service is temporarily unavailable.",
    *,
    reason: str = "dependency_unavailable",
) -> dict[str, Any]:
    """Return a fallback that does not invent data or claim an action succeeded."""
    return {
        "status": "fallback",
        "answer": message,
        "requires_human": True,
        "reason": reason,
        "actions_executed": False,
    }
