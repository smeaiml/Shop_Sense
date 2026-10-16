"""Guardrails for proposed refund actions."""

from typing import Any


def check_refund_action(
    amount_inr: float,
    order_value_inr: float,
    *,
    auto_cap_inr: float = 2000,
    evidence_verified: bool = False,
) -> dict[str, Any]:
    """Return a safe routing recommendation; never authorizes a payment side effect."""
    amount = float(amount_inr)
    order_value = float(order_value_inr)
    cap = float(auto_cap_inr)
    if amount <= 0 or order_value <= 0 or amount > order_value:
        return {
            "allowed_for_review": False,
            "requires_human": False,
            "approval_tier": None,
            "message": "Amount must be positive and cannot exceed the order value.",
            "executed": False,
        }
    if not evidence_verified:
        return {
            "allowed_for_review": False,
            "requires_human": True,
            "approval_tier": "human_review",
            "message": "Required evidence must be verified before the request can proceed.",
            "executed": False,
        }
    if amount > cap:
        tier = "team_lead" if amount <= 10000 else "ops_manager" if amount <= 50000 else "finance"
        return {
            "allowed_for_review": True,
            "requires_human": True,
            "approval_tier": tier,
            "message": "Preliminary checks only; human approval is required and no refund is issued.",
            "executed": False,
        }
    return {
        "allowed_for_review": True,
        "requires_human": False,
        "approval_tier": "auto_review",
        "message": "Preliminary checks only; no refund is approved or issued by this helper.",
        "executed": False,
    }
