"""FastAPI service for ShopSense support, order operations, and policy evidence."""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from capstone.agents.intake_agent import sanitize_customer_message
from capstone.agents.rag_agent import RAGAgent
from capstone.storage import (
    dashboard_stats,
    get_customer,
    get_customer_memory,
    get_ticket,
    initialize_store,
    list_tickets,
    update_customer_memory,
)
from capstone.tools.repository import lookup_order, reset_order_reliability
from capstone.workflows.approvals import validate_review_payload

logger = logging.getLogger(__name__)


class SupportChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=5000)
    customer_id: str | None = Field(default=None, max_length=80)
    order_id: str | None = Field(default=None, max_length=80)
    ticket_id: str | None = Field(default=None, max_length=80)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValueError("Provide a non-empty message without unsupported control characters.")
        return value


class SupportReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: str = Field(min_length=1, max_length=80)
    reviewer_id: str = Field(min_length=1, max_length=80)
    approved: bool
    note: str | None = Field(default=None, max_length=500)
    approver_role: str | None = Field(default=None, max_length=40)


class OrderLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_ref: str = Field(min_length=1, max_length=80)
    customer_ref: str = Field(min_length=1, max_length=80)


class PolicyQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=5000)
    order_id: str | None = Field(default=None, max_length=80)
    customer_id: str | None = Field(default=None, max_length=80)


class CustomerMemoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferences: list[str] = Field(max_length=20)


def _summary(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticket_id": str(ticket.get("ticket_id") or ""),
        "customer_id": ticket.get("customer_id"),
        "order_id": ticket.get("order_id"),
        "issue_type": str(ticket.get("issue_type") or "other"),
        "sentiment": str(ticket.get("sentiment") or "neutral"),
        "urgency": str(ticket.get("urgency") or "low"),
        "status": str(ticket.get("status") or "open"),
        "response": ticket.get("response"),
        "created_at": str(ticket.get("created_at") or datetime.now(timezone.utc).isoformat()),
        "approval_required": bool(ticket.get("approval_required")),
        "approval_tier": ticket.get("approval_tier"),
    }


def _workflow_result(ticket: dict[str, Any], thread_id: str | None = None) -> dict[str, Any]:
    return {
        "thread_id": str(thread_id or ticket.get("thread_id") or ticket.get("ticket_id") or ""),
        "ticket_id": str(ticket.get("ticket_id") or ""),
        "status": str(ticket.get("status") or "unknown"),
        "response": ticket.get("response"),
        "issue_type": ticket.get("issue_type"),
        "sentiment": ticket.get("sentiment"),
        "urgency": ticket.get("urgency"),
        "order_id": ticket.get("order_id"),
        "order_found": bool((ticket.get("order_data") or {}).get("found")),
        "decision": ticket.get("decision"),
        "decision_message": ticket.get("decision_message"),
        "approval_required": bool(ticket.get("approval_required")),
        "approval_tier": ticket.get("approval_tier"),
        "requires_human": bool(ticket.get("requires_human")),
        "human_review_reason": ticket.get("human_review_reason"),
        "citations": ticket.get("citations", []),
        "missing_fields": ticket.get("missing_fields", []),
        "refund_evaluation": ticket.get("refund_evaluation"),
        "errors": ticket.get("errors", []),
        "action_result": ticket.get("action_result"),
    }


def _memory_payload(customer_ref: str) -> dict[str, Any]:
    tickets = [
        _summary(ticket)
        for ticket in list_tickets(limit=200)
        if str(ticket.get("customer_id") or "").casefold() == customer_ref.casefold()
    ]
    tickets.sort(key=lambda item: item["created_at"], reverse=True)
    return {
        "customer_id": customer_ref.strip().upper(),
        "preferences": get_customer_memory(customer_ref),
        "recent_tickets": tickets[:20],
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_store()
    yield


app = FastAPI(
    title="ShopSense Customer Care API",
    description=(
        "Support intake, customer-scoped commerce lookups, policy evidence, "
        "persistent human review, and guarded mock actions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
router = APIRouter(prefix="/shopsense-backend")
rag_agent = RAGAgent()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ShopSense Customer Care API"}


@router.get("/dashboard")
def get_dashboard() -> dict[str, Any]:
    stats = dashboard_stats()
    stats["recent_tickets"] = [_summary(ticket) for ticket in stats["recent_tickets"]]
    return stats


@router.get("/tickets")
def get_tickets(
    status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    return [_summary(ticket) for ticket in list_tickets(status=status, limit=limit)]


@router.get("/reviews")
def get_pending_reviews() -> list[dict[str, Any]]:
    statuses = {"pending_human_review", "pending_approval"}
    return [
        _summary(ticket)
        for ticket in list_tickets(limit=200)
        if ticket.get("status") in statuses
    ]


@router.post("/support/chat")
def support_chat(request: SupportChatRequest) -> dict[str, Any]:
    existing = get_ticket(request.ticket_id) if request.ticket_id else None
    if existing:
        if (
            str(existing.get("customer_id") or "").casefold()
            != str(request.customer_id or "").casefold()
            or existing.get("raw_message") != request.message
            or (request.order_id and str(existing.get("order_id") or "").casefold() != request.order_id.casefold())
        ):
            raise HTTPException(status_code=409, detail="That ticket reference is already bound to a different request.")
        return _workflow_result(existing)

    try:
        from capstone.workflows.graph import invoke_support

        result = invoke_support(
            message=request.message,
            customer_id=request.customer_id,
            order_id=request.order_id,
            ticket_id=request.ticket_id,
        )
        return result
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="The support request could not be validated.") from exc
    except Exception as exc:
        logger.exception("support_workflow_failed")
        raise HTTPException(
            status_code=500,
            detail="The support workflow encountered an unexpected error.",
        ) from exc


@router.post("/support/review")
def support_review(request: SupportReviewRequest) -> dict[str, Any]:
    try:
        payload = validate_review_payload({
            "reviewer_id": request.reviewer_id,
            "approved": request.approved,
            "note": request.note,
            "approver_role": request.approver_role,
        })
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = get_ticket(request.thread_id)
    if not record or str(record.get("thread_id") or "") != request.thread_id:
        raise HTTPException(status_code=404, detail="Review request not found.")
    if record.get("status") not in {"pending_human_review", "pending_approval"}:
        # Repeated review submissions are read-only and cannot execute the action again.
        return _workflow_result(record, request.thread_id)
    if (
        request.approved
        and record.get("action_type") == "refund"
        and record.get("approval_required")
        and payload.get("approver_role") != str(record.get("approval_tier") or "").casefold()
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Approval from the required {record.get('approval_tier')} tier is needed.",
        )
    try:
        from capstone.workflows.graph import resume_support

        return resume_support(
            thread_id=request.thread_id,
            reviewer_id=payload["reviewer_id"],
            approved=payload["approved"],
            note=payload.get("note"),
            approver_role=payload.get("approver_role"),
        )
    except Exception as exc:
        logger.exception("support_review_resume_failed")
        raise HTTPException(
            status_code=409,
            detail="The workflow could not be resumed; no new action was submitted.",
        ) from exc


@router.post("/orders/lookup")
def lookup_customer_order(request: OrderLookupRequest) -> dict[str, Any]:
    result = lookup_order(request.order_ref, request.customer_ref)
    if result.get("service_error"):
        raise HTTPException(status_code=503, detail=result["message"])
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Order not found for this customer.")
    return result


@router.post("/policy/ask")
def ask_policy(request: PolicyQuestionRequest) -> dict[str, Any]:
    safe_question, has_injection = sanitize_customer_message(request.question)
    if not safe_question:
        return {
            "status": "insufficient_evidence",
            "answer": "I couldn't identify a policy question after removing untrusted instruction text. A human reviewer can help.",
            "requires_human": True,
            "citations": [],
            "evidence": [],
        }
    query = safe_question
    if request.order_id or request.customer_id:
        if not request.order_id or not request.customer_id:
            raise HTTPException(status_code=422, detail="Both order_id and customer_id are required for an order-specific policy answer.")
        order = lookup_order(request.order_id, request.customer_id)
        if order.get("service_error"):
            raise HTTPException(status_code=503, detail=order["message"])
        if not order.get("found"):
            raise HTTPException(status_code=404, detail="Order not found for this customer.")
        category = order.get("category")
        if category:
            query += f"\nVerified product category: {category}"
    result = rag_agent.answer(query)
    result["requires_human"] = result.get("status") == "insufficient_evidence"
    if has_injection:
        result["untrusted_instructions_removed"] = True
    return result


@router.get("/customers/{customer_ref}/memory")
def get_memory(customer_ref: str) -> dict[str, Any]:
    customer = get_customer(customer_ref)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return _memory_payload(customer_ref)


@router.put("/customers/{customer_ref}/memory")
def put_memory(customer_ref: str, request: CustomerMemoryRequest) -> dict[str, Any]:
    if not get_customer(customer_ref):
        raise HTTPException(status_code=404, detail="Customer not found.")
    for preference in request.preferences:
        if len(preference) > 240 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", preference):
            raise HTTPException(status_code=422, detail="A preference is too long or contains unsupported characters.")
    try:
        update_customer_memory(customer_ref, request.preferences)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _memory_payload(customer_ref)


app.include_router(router)


def run() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", os.environ.get("SHOP_SENSE_API_PORT", "8001")))
    uvicorn.run("capstone.api.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    run()
