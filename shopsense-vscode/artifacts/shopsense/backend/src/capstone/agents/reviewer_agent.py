"""Risk and grounding checks used before a support response is finalized."""

from typing import Any


def review_ticket(message: str, policy_answer: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return deterministic escalation signals; never approve a transaction."""
    text = (message or "").casefold()
    reasons = []
    if any(term in text for term in (
        "ignore previous instructions", "ignore all rules",
        "reveal your system prompt", "bypass policy",
    )):
        reasons.append("prompt_injection")
    if any(term in text for term in ("smoking", "smoke", "burning", "fire", "electric shock", "sparking")):
        reasons.append("product_safety")
    if any(term in text for term in ("consumer forum", "legal notice", "lawyer", "chargeback")):
        reasons.append("legal_escalation")
    if policy_answer and policy_answer.get("status") != "evidence_found":
        reasons.append("insufficient_policy_evidence")
    return {
        "requires_human": bool(reasons),
        "reasons": reasons,
        "decision": "escalate" if reasons else "continue",
    }
