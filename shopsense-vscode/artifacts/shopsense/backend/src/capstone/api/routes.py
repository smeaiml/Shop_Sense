"""TODO: Define request, status, human-approval and health endpoints. M8.

Scaffold only: no implementation is provided.
"""


"""API routes for ShopSense customer support."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from capstone.agents.rag_agent import RAGAgent
from capstone.tools.actions import evaluate_refund
from capstone.tools.repository import lookup_order

router = APIRouter()

# Load policy documents once when the routes module is imported.
rag_agent = RAGAgent()


class PolicyQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)


@router.get("/orders/{order_ref}")
def get_order(
    order_ref: str,
    customer_ref: str | None = Query(default=None),
):
    """Look up an order, optionally checking customer ownership."""
    result = lookup_order(order_ref, customer_ref=customer_ref)

    if not result.get("found"):
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result


@router.post("/policy/ask")
def ask_policy(request: PolicyQuestionRequest):
    """Retrieve relevant policy evidence and citations."""
    result = rag_agent.answer(request.question)

    if result["status"] == "insufficient_evidence":
        result["requires_human"] = True
    else:
        result["requires_human"] = False

    return result


@router.post("/refunds/evaluate")
def evaluate_refund_request(request: dict):
    """Placeholder route for refund evaluation.

    Keep the existing refund endpoint implementation in main.py
    if it already defines the request schema and evaluation logic.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Refund evaluation is not configured in routes.py. "
            "Use the existing refund evaluation endpoint in main.py."
        ),
    )

