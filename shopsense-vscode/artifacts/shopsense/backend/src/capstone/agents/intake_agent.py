import re
import logging
from typing import Any

from capstone.llm.client import classify_intake
from capstone.schemas.intake import (
    IssueType,
    Sentiment,
    SupportTicket,
    Urgency,
)

logger = logging.getLogger(__name__)
INJECTION_BLOCK = re.compile(
    r"\[(?:system\s+override|developer\s+message|system\s+message)[^\]]*\].*?\[(?:end\s+override|end\s+message)\]",
    re.IGNORECASE | re.DOTALL,
)
INJECTION_TERMS = (
    "ignore previous instructions",
    "ignore all rules",
    "reveal your system prompt",
    "bypass policy",
    "system override",
    "developer message",
)


def sanitize_customer_message(message: str) -> tuple[str, bool]:
    text = message.strip()
    found = any(term in text.casefold() for term in INJECTION_TERMS) or bool(INJECTION_BLOCK.search(text))
    safe_text = INJECTION_BLOCK.sub(" ", text).strip()
    return safe_text, found


def _model_fields(message: str) -> dict[str, Any]:
    """Return validated model labels or no result when the provider is unavailable."""
    try:
        output = classify_intake(message)
        if not output:
            return {}
        issue = IssueType(output.get("issue_type", "other"))
        sentiment = Sentiment(output.get("sentiment", "neutral"))
        urgency = Urgency(output.get("urgency", "medium"))
        return {"issue_type": issue, "sentiment": sentiment, "urgency": urgency}
    except Exception as exc:
        logger.warning("intake_classification_fallback", extra={"error_type": type(exc).__name__})
        return {}


def parse_ticket(
    message: str,
    ticket_id: str | None = None,
    customer_id: str | None = None,
) -> SupportTicket:
    """Parse common ShopSense support issues using deterministic rules."""

    text = message.strip()
    if not text:
        return SupportTicket(raw_message=message)
    # Strip clearly delimited override blocks before classification and routing.
    safe_text, has_injection = sanitize_customer_message(text)
    if not safe_text and has_injection:
        safe_text = " "
    lower = safe_text.casefold()

    # Accept dataset references (e.g. KW-O-000000) and conversational
    # references (e.g. ORDER-12345). Preserve the normalized token.
    dataset_match = re.search(r"\b[A-Z]{2}-O-\d{6}\b", safe_text, re.IGNORECASE)
    order_match = re.search(
        r"\border[-\s#:]+([A-Z0-9]+(?:-[A-Z0-9]+)*)\b",
        safe_text,
        re.IGNORECASE,
    )
    if dataset_match:
        order_id = dataset_match.group(0).upper()
    elif order_match:
        candidate = order_match.group(1).strip().upper()
        order_id = (
            candidate if candidate.startswith("ORDER")
            else f"ORDER-{candidate}"
        ) if any(character.isdigit() for character in candidate) else None
    else:
        order_id = None

    # Identify the issue type.
    if any(word in lower for word in ("damaged", "broken", "defective")):
        issue_type = IssueType.DAMAGED_ITEM
    elif any(word in lower for word in ("refund", "money back", "reimburse", "get back", "approve it")):
        issue_type = IssueType.REFUND
    elif any(word in lower for word in ("replacement", "replace", "exchange")):
        issue_type = IssueType.REPLACEMENT
    elif any(word in lower for word in ("return", "send it back")):
        issue_type = IssueType.RETURN
    elif any(word in lower for word in ("late", "delayed", "tracking", "delivery", "shipped")):
        issue_type = IssueType.SHIPPING
    elif any(word in lower for word in ("warranty", "repair")):
        issue_type = IssueType.WARRANTY
    else:
        issue_type = IssueType.OTHER

    # Basic sentiment and urgency heuristics.
    angry_terms = ("furious", "scam", "unacceptable", "ridiculous", "worst")
    negative_terms = ("disappointed", "upset", "bad", "problem", "wrong")

    if any(term in lower for term in angry_terms):
        sentiment = Sentiment.ANGRY
    elif any(term in lower for term in negative_terms + ("damaged", "broken", "defective")):
        sentiment = Sentiment.NEGATIVE
    else:
        sentiment = Sentiment.NEUTRAL

    if sentiment == Sentiment.ANGRY or any(
        term in lower for term in ("urgent", "immediately", "asap")
    ):
        urgency = Urgency.HIGH
    elif sentiment == Sentiment.NEGATIVE:
        urgency = Urgency.MEDIUM
    else:
        urgency = Urgency.LOW

    amount_match = re.search(
        r"(?:₹|inr\s*)\s*([\d,]+(?:\.\d{1,2})?)|"
        r"\b([\d,]+(?:\.\d{1,2})?)\s*(?:inr|rupees)\b",
        lower,
    )
    amount_text = next((group for group in amount_match.groups() if group), None) if amount_match else None
    amount = float(amount_text.replace(",", "")) if amount_text else None

    missing_fields = []
    if not order_id:
        missing_fields.append("order_id")
    if issue_type == IssueType.OTHER:
        missing_fields.append("issue_type")

    # Ask the model to classify only sanitized customer content. Structured
    # labels are constrained to enums and never authorize business actions.
    model_fields = _model_fields(safe_text) if not has_injection else {}
    if model_fields:
        issue_type = model_fields["issue_type"]
        sentiment = model_fields["sentiment"]
        urgency = model_fields["urgency"]
        if issue_type != IssueType.OTHER:
            missing_fields = [field for field in missing_fields if field != "issue_type"]
    requires_human = has_injection and issue_type in {
        IssueType.OTHER,
        IssueType.REFUND,
        IssueType.REPLACEMENT,
        IssueType.RETURN,
        IssueType.DAMAGED_ITEM,
    }

    return SupportTicket(
        ticket_id=ticket_id,
        customer_id=customer_id,
        order_id=order_id,
        raw_message=text,
        issue_type=issue_type,
        sentiment=sentiment,
        urgency=urgency,
        claimed_amount_inr=amount,
        missing_fields=missing_fields,
        requires_human=requires_human,
        contains_untrusted_instructions=has_injection,
    )
