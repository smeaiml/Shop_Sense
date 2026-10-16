"""Safe wrapper around deterministic ShopSense refund policy evaluation."""

from typing import Any

from capstone.tools.actions import evaluate_refund


def evaluate_action(
    order_ref: str,
    customer_ref: str,
    reason_code: str,
    requested_amount_inr: float | None = None,
    **verified_evidence: Any,
) -> dict[str, Any]:
    """Evaluate a proposed action; never executes or issues a refund.

    Evidence flags must come from a trusted backend, not raw customer text.
    """
    allowed = {
        "reported_damaged_within_period",
        "photo_provided",
        "parcel_declared_lost_or_dispute_upheld",
        "customer_refuses_or_returns_late_order",
        "inside_return_window",
        "cancelled_before_dispatch",
        "evaluation_date",
    }
    unsupported = set(verified_evidence) - allowed
    if unsupported:
        raise ValueError(f"Unsupported evaluation fields: {sorted(unsupported)}")
    return evaluate_refund(
        order_ref=order_ref,
        customer_ref=customer_ref,
        reason_code=reason_code,
        requested_amount_inr=requested_amount_inr,
        **verified_evidence,
    )
