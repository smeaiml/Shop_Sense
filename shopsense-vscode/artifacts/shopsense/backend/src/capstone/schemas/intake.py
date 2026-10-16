from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IssueType(str, Enum):
    RETURN = "return"
    REFUND = "refund"
    REPLACEMENT = "replacement"
    SHIPPING = "shipping"
    DAMAGED_ITEM = "damaged_item"
    WARRANTY = "warranty"
    OTHER = "other"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ANGRY = "angry"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SupportTicket(BaseModel):
    """Validated representation of a ShopSense customer support request."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ticket_id: Optional[str] = None
    customer_id: Optional[str] = None
    order_id: Optional[str] = None

    raw_message: str = Field(min_length=1, max_length=5000)
    issue_type: IssueType = IssueType.OTHER
    sentiment: Sentiment = Sentiment.NEUTRAL
    urgency: Urgency = Urgency.MEDIUM

    claimed_amount_inr: Optional[float] = Field(default=None, ge=0)
    missing_fields: list[str] = Field(default_factory=list)
    requires_human: bool = False
    contains_untrusted_instructions: bool = False

    @field_validator("raw_message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A support message is required.")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValueError("The support message contains unsupported control characters.")
        return value

    @field_validator("ticket_id", "customer_id", "order_id")
    @classmethod
    def validate_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if len(value) > 80 or not all(char.isalnum() or char in "-_." for char in value):
            raise ValueError("References may contain only letters, numbers, dots, hyphens, and underscores.")
        return value.upper()
