"""API request/response schemas for ShopSense support workflows."""

from typing import Any

from pydantic import BaseModel, Field


class SupportResponse(BaseModel):
    thread_id: str
    ticket_id: str
    status: str
    response: str | None = None
    issue_type: str | None = None
    sentiment: str | None = None
    urgency: str | None = None
    order_id: str | None = None
    order_found: bool = False
    decision: str | None = None
    decision_message: str | None = None
    refund_evaluation: dict[str, Any] | None = None
    approval_required: bool = False
    approval_tier: str | None = None
    requires_human: bool = False
    human_review_reason: str | None = None
    citations: list[dict[str, str]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    interrupts: list[dict[str, Any]] = Field(default_factory=list)
    reviewer_id: str | None = None
    review_approved: bool | None = None


class SupportChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    customer_id: str | None = Field(default=None, min_length=1, max_length=100)
    order_id: str | None = Field(default=None, min_length=1, max_length=100)
    ticket_id: str | None = Field(default=None, min_length=1, max_length=100)


class HumanReviewRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    reviewer_id: str = Field(min_length=1, max_length=100)
    approved: bool
    note: str | None = Field(default=None, max_length=1000)
