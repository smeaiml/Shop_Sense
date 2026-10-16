"""Human escalation specialist and review-payload validator."""

from typing import Any

from capstone.workflows.approvals import validate_review_payload


class EscalationReviewer:
    @staticmethod
    def validate(payload: dict[str, Any]) -> dict[str, Any]:
        return validate_review_payload(payload)

    @staticmethod
    def should_escalate(*, sentiment: str, safety_risk: bool, legal_risk: bool, approval_required: bool) -> bool:
        return (
            sentiment == "angry"
            or safety_risk
            or legal_risk
            or approval_required
        )
