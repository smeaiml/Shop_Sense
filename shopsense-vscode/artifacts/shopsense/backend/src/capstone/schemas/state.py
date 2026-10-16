"""Typed state shared across the ShopSense support workflow."""



from typing import Any, TypedDict
from typing_extensions import NotRequired


class WorkflowState(TypedDict, total=False):
    """State passed through triage, evidence retrieval, decision and review."""

    ticket_id: str | None
    customer_id: str | None
    order_id: str | None
    raw_message: str
    safe_message: str
    contains_untrusted_instructions: bool
    issue_type: str
    sentiment: str
    urgency: str
    claimed_amount_inr: float | None
    missing_fields: list[str]

    order_data: dict[str, Any] | None
    policy_answer: dict[str, Any] | None
    citations: list[dict[str, str]]
    refund_evaluation: dict[str, Any] | None
    reason_code: str | None

    decision: str | None
    decision_message: str | None
    action_ready: bool
    action_type: str | None
    action_result: dict[str, Any] | None
    approval_required: bool
    approval_tier: str | None
    requires_human: bool
    human_review_reason: str | None
    status: str
    response: str | None
    errors: list[str]
    audit_events: list[dict[str, Any]]
    reviewer_id: str | None
    approval_role: str | None
    review_note: str | None
    review_approved: bool | None
