"""Human-review payload validation and workflow interrupt helpers."""

from typing import Any


def validate_review_payload(payload: Any) -> dict[str, Any]:
    """Validate an explicit reviewer decision before resuming a paused graph."""
    if not isinstance(payload, dict):
        raise ValueError("review payload must be an object")
    reviewer_id = payload.get("reviewer_id")
    approved = payload.get("approved")
    note = payload.get("note")
    approver_role = payload.get("approver_role")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ValueError("reviewer_id is required")
    if not isinstance(approved, bool):
        raise ValueError("approved must be a boolean")
    if note is not None and not isinstance(note, str):
        raise ValueError("note must be text")
    if isinstance(note, str) and len(note) > 1000:
        raise ValueError("note must be 1000 characters or fewer")
    if approver_role is not None and (
        not isinstance(approver_role, str)
        or approver_role.strip().lower() not in {"agent", "team_lead", "ops_manager", "finance"}
    ):
        raise ValueError("approver_role must be an authorized refund tier")
    return {
        "reviewer_id": reviewer_id.strip(),
        "approved": approved,
        "note": note.strip() if isinstance(note, str) and note.strip() else None,
        "approver_role": approver_role.strip().lower() if isinstance(approver_role, str) else None,
    }
