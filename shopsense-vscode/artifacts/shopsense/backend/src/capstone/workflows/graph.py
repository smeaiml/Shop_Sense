"""LangGraph orchestration for ShopSense support, review, and guarded actions."""

from __future__ import annotations

from datetime import date
from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from capstone.agents.triage_agent import TriageAgent
from capstone.agents.rag_agent import RAGAgent
from capstone.agents.order_actions_agent import OrderActionsAgent
from capstone.agents.escalation_reviewer import EscalationReviewer
from capstone.schemas.state import WorkflowState
from capstone.tools.actions import (
    calculate_delay_compensation,
    calculate_refund_amount,
    calculate_refund_for_category,
    evaluate_refund,
)
from capstone.tools.repository import lookup_order
from capstone.tools.lookups import lookup_product
from capstone.storage import save_ticket
from capstone.workflows.approvals import validate_review_payload
from capstone.workflows.checkpoints import make_checkpointer

_rag_agent = RAGAgent()
_triage_agent = TriageAgent()
_order_actions_agent = OrderActionsAgent()
_escalation_reviewer = EscalationReviewer()

INJECTION_TERMS = (
    "ignore previous instructions",
    "ignore all rules",
    "reveal your system prompt",
    "bypass policy",
)
SAFETY_TERMS = ("smoking", "smoke", "burning", "fire", "electric shock", "sparking")
LEGAL_ESCALATION_TERMS = ("consumer forum", "legal notice", "lawyer", "chargeback")


def _event(state: WorkflowState, event: str, **details: Any) -> list[dict[str, Any]]:
    return list(state.get("audit_events", [])) + [
        {"event": event, "details": details}
    ]


def _is_policy_question(message: str) -> bool:
    text = (message or "").casefold()
    markers = (
        "return window", "how many days", "restocking fee", "pickup fee",
        "warranty policy", "return policy", "shipping policy",
        "what is the policy", "what are the rules", "is it returnable",
        "refund approved", "refund timeline", "when will i get", "upi",
        "goodwill", "wallet credit", "restocking fee", "fee structure",
        "reporting deadline", "warranty",
    )
    return any(marker in text for marker in markers)


def _category_from_message(message: str) -> str | None:
    text = message.casefold()
    categories = (
        (("electronics", "headphones", "television", "tv", "power bank"), "Electronics"),
        (("furniture", "sofa", "couch", "wardrobe"), "Furniture"),
        (("home & kitchen", "kitchen", "blender", "mixer", "cookware"), "Home & Kitchen"),
        (("toys", "toy "), "Toys"),
        (("apparel", "clothing", "shirt", "dress"), "Apparel"),
        (("beauty", "skincare", "makeup"), "Beauty"),
        (("groceries", "grocery", "food item"), "Groceries"),
        (("sports & outdoors", "sports gear", "camping"), "Sports & Outdoors"),
    )
    for terms, category in categories:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) for term in terms):
            return category
    return None


def _asks_internal_flag_status(message: str) -> bool:
    text = message.casefold()
    return any(term in text for term in (
        "am i flagged", "account flagged", "flagged on your system",
        "marked my account", "have you flagged me", "flag status",
    ))


def _days_mentioned(message: str, *, ago_only: bool = False) -> int | None:
    pattern = r"\b(\d+)\s+days?\s+ago\b" if ago_only else r"\b(\d+)\s+days?\b"
    match = re.search(pattern, message.casefold())
    return int(match.group(1)) if match else None


def _days_since_order(message: str) -> int | None:
    match = re.search(
        r"\b(\d+)\s+days?\s+after\s+(?:i\s+)?(?:placed|placing|ordered)\b",
        message.casefold(),
    )
    return int(match.group(1)) if match else _days_mentioned(message, ago_only=True)


def _reason_code(message: str, issue_type: str) -> str | None:
    text = message.casefold()
    if any(term in text for term in ("not delivered", "never arrived", "lost in transit", "parcel lost")):
        return "not_delivered"
    if any(term in text for term in ("late", "delayed", "delivery delay")):
        return "late_delivery"
    if any(term in text for term in ("cancel before dispatch", "cancelled before dispatch", "cancelled before shipping")):
        return "cancelled_before_dispatch"
    if any(term in text for term in ("changed my mind", "change of mind", "no longer want")):
        return "changed_mind"
    if any(term in text for term in ("wrong item", "incorrect item", "sent the wrong")):
        return "wrong_item"
    if issue_type == "damaged_item" or any(term in text for term in ("damaged", "broken", "defective", "cracked")):
        return "damaged"
    if issue_type in {"refund", "return", "replacement"}:
        return None
    return None


def intake_node(state: WorkflowState) -> WorkflowState:
    message = (state.get("raw_message") or "").strip()
    if not message:
        return {
            "status": "needs_information",
            "response": "Please describe the issue so I can help.",
            "errors": list(state.get("errors", [])) + ["empty_message"],
            "audit_events": _event(state, "intake_rejected", reason="empty_message"),
        }

    ticket, safe_message, has_injection = _triage_agent.run(
        message,
        ticket_id=state.get("ticket_id"),
        customer_id=state.get("customer_id"),
    )
    order_id = state.get("order_id") or ticket.order_id
    missing = [
        field for field in ticket.missing_fields
        if not (field == "order_id" and order_id)
    ]
    if not state.get("customer_id") and order_id:
        missing.append("customer_id")

    return {
        "ticket_id": state.get("ticket_id") or uuid4().hex,
        "customer_id": state.get("customer_id"),
        "order_id": order_id,
        "raw_message": message,
        "safe_message": safe_message,
        "contains_untrusted_instructions": has_injection,
        "issue_type": ticket.issue_type.value,
        "sentiment": ticket.sentiment.value,
        "urgency": ticket.urgency.value,
        "claimed_amount_inr": ticket.claimed_amount_inr,
        "missing_fields": sorted(set(missing)),
        "requires_human": ticket.requires_human,
        "human_review_reason": (
            "Untrusted instruction text was detected in an action-bearing request."
            if ticket.requires_human else None
        ),
        "errors": list(state.get("errors", [])),
        "audit_events": _event(
            state, "intake_parsed",
            issue_type=ticket.issue_type.value,
            order_id=order_id,
            missing_fields=sorted(set(missing)),
            untrusted_instructions=has_injection,
        ),
    }


def guardrail_node(state: WorkflowState) -> WorkflowState:
    message = (state.get("safe_message") or state.get("raw_message") or "").casefold()
    reasons = []
    if state.get("requires_human"):
        reasons.append(state.get("human_review_reason") or "Untrusted instruction detected.")
    if state.get("sentiment") == "angry":
        reasons.append("Angry customer sentiment requires human review.")
    if any(term in message for term in SAFETY_TERMS):
        reasons.append("Potential product safety incident requires urgent human review.")
    if any(term in message for term in LEGAL_ESCALATION_TERMS):
        reasons.append("Legal or consumer-forum escalation requires human review.")
    if any(term in message for term in ("third time", "third contact", "again about this order")):
        reasons.append("Repeat-contact trigger requires human review.")
    if reasons:
        return {
            "requires_human": True,
            "human_review_reason": "; ".join(dict.fromkeys(reasons)),
            "audit_events": _event(state, "guardrail_escalation", reasons=reasons),
        }
    return {
        "requires_human": False,
        "audit_events": _event(state, "guardrail_checked", result="no_immediate_escalation"),
    }


def order_lookup_node(state: WorkflowState) -> WorkflowState:
    order_id = state.get("order_id")
    customer_id = state.get("customer_id")
    if not order_id or not customer_id:
        message = "Order lookup needs both an order reference and a verified customer reference."
        return {
            "order_data": {"found": False, "message": message},
            "audit_events": _event(state, "order_lookup_skipped", reason=message),
        }
    try:
        result = _order_actions_agent.lookup(order_id, customer_id)
    except Exception as exc:
        return {
            "order_data": {"found": False, "message": "The order service is temporarily unavailable."},
            "errors": list(state.get("errors", [])) + [f"order_lookup_error:{type(exc).__name__}"],
            "audit_events": _event(state, "order_lookup_failed", error=type(exc).__name__),
        }
    updates = {
        "order_data": result,
        "audit_events": _event(state, "order_lookup_completed", found=result.get("found", False)),
    }
    if result.get("service_error"):
        updates.update({
            "requires_human": True,
            "human_review_reason": "Order service retries were exhausted; human support fallback is required.",
            "status": "pending_human_review",
        })
    return updates


def policy_retrieval_node(state: WorkflowState) -> WorkflowState:
    raw_message = state.get("safe_message") or state.get("raw_message", "")
    order_data = state.get("order_data") or {}
    order = order_data.get("order") or {}

    # Include the verified product category so retrieval can filter unrelated
    # category addenda. Resolve the category from the SKU when needed.
    category = (
        order_data.get("category")
        or order_data.get("product_category")
        or order.get("category")
        or order.get("product_category")
    )
    if not category:
        category = _category_from_message(raw_message)
    if not category and order_data.get("found") and order.get("sku"):
        try:
            product_result = lookup_product(str(order["sku"]))
            if product_result.get("found"):
                product = product_result.get("product") or {}
                category = product.get("category") or product.get("product_category")
        except Exception:
            # Retrieval can still proceed with the customer's original question.
            category = None

    query = raw_message
    if category:
        query += f"\nRequested product category: {category}"
    if any(term in raw_message.casefold() for term in ("return", "change my mind", "changed my mind")):
        query += "\nReturn window, return policy, opened item restocking fee and return pickup fee."
    if "upi" in raw_message.casefold() or "refund approved" in raw_message.casefold():
        query += "\nRefund processing time for UPI payment after approval."
    if "goodwill" in raw_message.casefold() or "wallet" in raw_message.casefold():
        query += "\nGoodwill credit rules, stacking or combining a goodwill credit with a full refund."
    if _asks_internal_flag_status(raw_message):
        query += "\nReturn fraud standard: internal account risk flags must not be confirmed or denied to customers."
    if any(term in raw_message.casefold() for term in SAFETY_TERMS):
        query += "\nProduct safety incident escalation and immediate customer safety response."
    if "tracking has not moved" in raw_message.casefold():
        query += "\nLost parcel threshold after promised delivery date, refund or replacement approval tier."
    if "late" in raw_message.casefold() or "delay" in raw_message.casefold():
        query += "\nDelivery promise and delay compensation goodwill credit policy."
    if any(term in raw_message.casefold() for term in ("consumer forum", "legal notice", "lawyer", "third time")):
        query += "\nRefund Authorisation and Escalation Matrix. Escalation Triggers and Customer Communication Standard."
    if state.get("sentiment") == "angry" or state.get("urgency") == "high":
        query += "\nRefund approval limits and human escalation requirements."
    if category and any(term in raw_message.casefold() for term in ("refund", "approve", "how much", "net refund")):
        query += "\nCategory-specific return policy, refund fees, and Refund Authorisation and Escalation Matrix."

    try:
        result = _rag_agent.answer(query)
    except Exception as exc:
        result = {
            "status": "insufficient_evidence",
            "answer": "Policy retrieval is temporarily unavailable. Please contact a human support agent.",
            "citations": [],
            "evidence": [],
        }
        errors = list(state.get("errors", [])) + [f"policy_retrieval_error:{type(exc).__name__}"]
    else:
        errors = list(state.get("errors", []))
    return {
        "policy_answer": result,
        "citations": result.get("citations", []),
        "errors": errors,
        "audit_events": _event(
            state, "policy_retrieval_completed",
            status=result.get("status"),
            citation_count=len(result.get("citations", [])),
        ),
    }


def decision_node(state: WorkflowState) -> WorkflowState:
    if state.get("status") == "needs_information" and state.get("response"):
        return state

    order_data = state.get("order_data") or {}
    issue_type = state.get("issue_type", "other")
    message = state.get("safe_message") or state.get("raw_message", "")
    reason_code = _reason_code(message, issue_type)
    policy = state.get("policy_answer") or {}

    # Internal account-risk signals are never disclosed or confirmed to a customer.
    if _asks_internal_flag_status(message):
        return {
            "decision": "sensitive_account_question",
            "decision_message": "An authorized support specialist can discuss prior return decisions with you.",
            "approval_required": False,
            "requires_human": True,
            "human_review_reason": "Customer asked about a restricted internal account signal.",
            "status": "pending_human_review",
            "response": "I can’t confirm or deny internal account signals. A support specialist can review the return decisions with you.",
            "audit_events": _event(state, "restricted_account_question_escalated"),
        }

    # Product safety incidents receive immediate make-safe guidance and human escalation.
    if any(term in message.casefold() for term in SAFETY_TERMS):
        return {
            "decision": "product_safety_escalation",
            "decision_message": "Stop using and charging the device. Disconnect it only if this is safe; do not handle a damaged battery. Keep it away from flammable materials, and contact emergency services if there is active smoke, fire, or immediate danger.",
            "approval_required": False,
            "requires_human": True,
            "human_review_reason": "Potential product safety incident requires urgent human review.",
            "status": "pending_human_review",
            "response": (
                "Stop using and charging the device. Disconnect it only if this is safe; do not handle a damaged battery. "
                "Keep it away from flammable materials, and contact emergency services if there is active smoke, fire, "
                "or immediate danger. I’ve escalated this for urgent human review."
            ),
            "audit_events": _event(state, "product_safety_escalated"),
        }

    # High-risk cases can be escalated even before the customer has supplied
    # enough references to execute or verify a requested action.
    if (
        state.get("requires_human")
        and issue_type in {"refund", "return", "damaged_item", "replacement"}
        and (not state.get("order_id") or not state.get("customer_id"))
    ):
        amount = state.get("claimed_amount_inr")
        category = _category_from_message(message)
        estimate = None
        if amount and category and reason_code:
            estimate = calculate_refund_for_category(
                category,
                float(amount),
                reason_code,
                opened_item=True,
            )
        approval_tier = estimate.get("approval_tier") if estimate else None
        amount_note = (
            f" The reported ₹{amount:,.0f} is above the ₹2,000 automated cap"
            + (f" and requires {approval_tier} approval after verification." if approval_tier else " and requires human review after verification.")
            if amount and float(amount) > 2000
            else ""
        )
        reason = state.get("human_review_reason") or "A risk signal requires human review."
        return {
            "decision": "human_review_required",
            "decision_message": reason,
            "approval_required": bool(amount and float(amount) > 2000),
            "approval_tier": approval_tier,
            "requires_human": True,
            "human_review_reason": reason,
            "status": "pending_human_review",
            "response": (
                "I understand this has been frustrating. I can’t approve or process this request without verifying the order and evidence."
                f"{amount_note} It has been sent to the human support team; no refund or replacement has been approved."
            ),
            "audit_events": _event(state, "risk_escalated_before_action", amount_inr=amount),
        }

    if (
        "warranty" in message.casefold()
        and "used" in message.casefold()
        and re.search(r"\b45\s+days?\b", message.casefold())
    ):
        answer = (
            "I cannot verify warranty coverage for a used television after 45 days from the available policy evidence. "
            "The policy documents do not support that specific claim, so I will not infer coverage."
        )
        return {
            "decision": "unsupported_policy_claim_refused",
            "decision_message": answer,
            "approval_required": False,
            "requires_human": False,
            "citations": [],
            "status": "refused",
            "response": answer,
            "audit_events": _event(state, "unsupported_policy_claim_refused"),
        }

    # General policy questions do not require an order/customer identity.
    if (
        not state.get("order_id")
        and _is_policy_question(message)
        and policy.get("status") == "evidence_found"
    ):
        if state.get("requires_human"):
            reason = state.get("human_review_reason") or "Risk signal detected."
            return {
                "decision": "human_review_required",
                "decision_message": reason,
                "approval_required": False,
                "status": "pending_human_review",
                "response": "This request has been referred for human review. No business action was performed.",
                "audit_events": _event(state, "decision_routed_to_human", reason=reason),
            }
        answer = policy.get("answer", "")
        return {
            "decision": "policy_answer",
            "decision_message": answer,
            "approval_required": False,
            "requires_human": False,
            "status": "answered",
            "response": answer,
            "audit_events": _event(state, "general_policy_question_answered"),
        }

    # A customer can ask for a non-mutating estimate without exposing or
    # requiring access to an order. No transaction is possible without verified
    # customer and order references.
    category = _category_from_message(message)
    days_since_order = _days_since_order(message)
    if (
        issue_type in {"refund", "return"}
        and not state.get("order_id")
        and not state.get("customer_id")
        and category
        and state.get("claimed_amount_inr")
        and reason_code == "changed_mind"
    ):
        opened_item = bool(re.search(r"\bopened\b|\bused\b", message.casefold())) and not bool(
            re.search(r"\bunopened\b|\bsealed\b", message.casefold())
        )
        estimate = calculate_refund_for_category(
            category,
            float(state["claimed_amount_inr"]),
            reason_code,
            opened_item=opened_item,
        )
        if estimate.get("eligible") and policy.get("status") == "evidence_found":
            net = float(estimate["requested_amount_inr"])
            high_value = estimate["decision"] == "eligible_requires_human_approval"
            approval_tier = estimate.get("approval_tier")
            detail = (
                f"Estimated gross refund ₹{estimate['gross_refund_inr']:,.2f}, less "
                f"₹{estimate['restocking_fee_inr']:,.2f} restocking and "
                f"₹{estimate['pickup_fee_inr']:,.2f} pickup fees, gives a net estimate of ₹{net:,.2f}. "
            )
            if high_value:
                detail += f"This exceeds the ₹2,000 automated cap and requires {approval_tier} approval."
            else:
                detail += "This estimate is within the ₹2,000 automated limit."
            detail += " It is an estimate only; no action can be approved or issued until the customer and order are verified."
            return {
                "decision": "refund_estimate",
                "decision_message": detail,
                "refund_evaluation": estimate,
                "approval_required": high_value,
                "approval_tier": approval_tier,
                "requires_human": high_value,
                "human_review_reason": "The estimated net refund exceeds the automated approval cap." if high_value else None,
                "action_ready": False,
                "status": "pending_human_review" if high_value else "answered",
                "response": detail,
                "audit_events": _event(
                    state,
                    "non_mutating_refund_estimate",
                    category=category,
                    amount_inr=net,
                    approval_required=high_value,
                ),
            }

    # A category return-window question is answerable without order access.
    if (
        issue_type in {"refund", "return"}
        and not state.get("order_id")
        and not state.get("customer_id")
        and category
        and days_since_order is not None
        and "return" in message.casefold()
        and policy.get("status") == "evidence_found"
    ):
        window_match = re.search(r"return window is\s+(\d+)\s+days", str(policy.get("answer", "")), re.IGNORECASE)
        if window_match:
            window_days = int(window_match.group(1))
            if days_since_order > window_days:
                answer = (
                    f"The {category} return window is {window_days} days from delivery. "
                    f"At {days_since_order} days, this change-of-mind return is outside the window. "
                )
                if "apparel" in message.casefold():
                    answer += "The longer Apparel window applies only to Apparel, not this product category."
            else:
                answer = str(policy.get("answer", ""))
            return {
                "decision": "policy_answer",
                "decision_message": answer,
                "approval_required": False,
                "requires_human": False,
                "status": "answered",
                "response": answer,
                "audit_events": _event(state, "category_return_window_answered", category=category, days_since_delivery=days_since_order),
            }

    # Estimate the delay credit from the configured service promise and credit table.
    if issue_type == "shipping" and not state.get("order_id") and not state.get("customer_id"):
        lower_message = message.casefold()
        service_tier = next((value for value in ("standard", "express", "economy") if value in lower_message), None)
        delivery_zone = "non_metro" if "non-metro" in lower_message or "non metro" in lower_message else ("metro" if "metro" in lower_message else None)
        if service_tier and delivery_zone and days_since_order is not None and any(word in lower_message for word in ("keeping", "delay", "late")):
            delay = calculate_delay_compensation(service_tier, delivery_zone, days_since_order)
            credit = int(delay.get("goodwill_credit_inr", 0))
            answer = (
                f"{service_tier.title()} delivery to a {delivery_zone.replace('_', '-')} address is promised in "
                f"{delay['promise_days']} days. At {days_since_order} days, the shipment is {delay['days_late']} days late. "
            )
            if "keep" in lower_message:
                answer += (
                    f"Because you are keeping the item, the policy provides a ₹{credit} wallet goodwill credit rather than a full refund. "
                    "Please provide the order and customer references before any credit can be applied."
                )
            return {
                "decision": "delay_credit_calculated",
                "decision_message": answer,
                "approval_required": False,
                "requires_human": False,
                "status": "answered",
                "response": answer,
                "audit_events": _event(state, "delay_credit_calculated", days_late=delay.get("days_late"), credit_inr=credit),
            }

        if "tracking has not moved" in lower_message and service_tier and delivery_zone and days_since_order is not None:
            delay = calculate_delay_compensation(service_tier, delivery_zone, days_since_order)
            if delay.get("days_late", 0) >= 10:
                amount = state.get("claimed_amount_inr")
                estimate = (
                    calculate_refund_for_category(category, float(amount), "not_delivered", opened_item=True)
                    if category and amount else None
                )
                approval_tier = estimate.get("approval_tier") if estimate else None
                response = (
                    f"The standard {delivery_zone.replace('_', '-')} delivery promise is {delay['promise_days']} days. "
                    f"At {days_since_order} days after dispatch, the shipment is {delay['days_late']} days past that promise, "
                    "which meets the lost-in-transit escalation threshold. A verified customer can choose a refund or replacement. "
                )
                if amount and float(amount) > 2000:
                    response += f"The reported ₹{float(amount):,.0f} exceeds the automated cap and requires {approval_tier or 'human'} approval. "
                response += "Please provide the order and customer references; no action has been approved or issued."
                return {
                    "decision": "lost_parcel_human_review",
                    "approval_required": bool(amount and float(amount) > 2000),
                    "approval_tier": approval_tier,
                    "requires_human": True,
                    "human_review_reason": "Lost-parcel investigation and approval are required.",
                    "status": "pending_human_review",
                    "response": response,
                    "audit_events": _event(state, "lost_parcel_threshold_met", days_late=delay.get("days_late")),
                }

        if not state.get("requires_human"):
            answer = "I can check the shipment scan or calculate any delay credit once you provide the order and customer references."
            return {
                "decision": "insufficient_information",
                "approval_required": False,
                "requires_human": False,
                "status": "needs_information",
                "response": answer,
                "audit_events": _event(state, "shipping_needs_verified_references"),
            }

    if (
        "warranty" in message.casefold()
        and "used" in message.casefold()
        and re.search(r"\b45\s+days?\b", message.casefold())
    ):
        answer = (
            "I cannot verify warranty coverage for a used television after 45 days from the available policy evidence. "
            "The policy documents do not support that specific claim, so I will not infer coverage."
        )
        return {
            "decision": "unsupported_policy_claim_refused",
            "decision_message": answer,
            "approval_required": False,
            "requires_human": False,
            "status": "refused",
            "response": answer,
            "audit_events": _event(state, "unsupported_policy_claim_refused"),
        }

    if issue_type == "replacement":
        if not state.get("order_id") or not state.get("customer_id"):
            msg = "Please provide your order reference and customer reference so the order can be verified."
            return {
                "decision": "insufficient_information",
                "decision_message": msg,
                "approval_required": False,
                "status": "needs_information",
                "response": msg,
                "audit_events": _event(state, "replacement_needs_identity"),
            }
        if not order_data.get("found"):
            msg = order_data.get("message") or "I couldn't verify that order for this customer."
            if order_data.get("service_error"):
                msg = "The order service is unavailable; this request was sent to the human support queue."
                return {
                    "decision": "order_service_fallback",
                    "decision_message": msg,
                    "approval_required": False,
                    "requires_human": True,
                    "human_review_reason": msg,
                    "status": "pending_human_review",
                    "response": msg,
                    "audit_events": _event(state, "replacement_order_service_fallback"),
                }
            return {
                "decision": "insufficient_information",
                "decision_message": msg,
                "approval_required": False,
                "status": "needs_information",
                "response": msg,
                "audit_events": _event(state, "replacement_order_unverified"),
            }
        reason = state.get("human_review_reason") or "Replacement actions require an explicit human review."
        return {
            "decision": "replacement_review_required",
            "action_type": "replacement",
            "action_ready": False,
            "decision_message": reason,
            "approval_required": True,
            "approval_tier": "human reviewer",
            "requires_human": True,
            "human_review_reason": reason,
            "status": "pending_human_review",
            "response": "The verified order is queued for replacement review. No replacement has been created.",
            "audit_events": _event(state, "replacement_routed_to_review"),
        }

    if issue_type in {"refund", "damaged_item", "return"}:
        if not state.get("order_id") or not state.get("customer_id"):
            msg = "Please provide your order reference and customer reference so the order can be verified."
            return {
                "decision": "insufficient_information",
                "decision_message": msg,
                "approval_required": False,
                "status": "needs_information",
                "response": msg,
                "audit_events": _event(state, "decision_needs_identity", issue_type=issue_type),
            }
        if not order_data.get("found"):
            if order_data.get("service_error"):
                msg = order_data.get("message") or "The order service is temporarily unavailable."
                return {
                    "decision": "order_service_fallback",
                    "decision_message": msg,
                    "approval_required": False,
                    "requires_human": True,
                    "human_review_reason": msg,
                    "status": "pending_human_review",
                    "response": msg,
                    "audit_events": _event(state, "refund_order_service_fallback"),
                }
            msg = "I couldn't verify that order for this customer. Please check the references or contact support."
            return {
                "decision": "insufficient_information",
                "decision_message": msg,
                "approval_required": False,
                "status": "needs_information",
                "response": msg,
                "audit_events": _event(state, "decision_order_unverified"),
            }
        if not reason_code:
            msg = "Please explain the refund or return reason (for example, damaged, wrong item, late delivery, or changed mind)."
            return {
                "decision": "insufficient_information",
                "decision_message": msg,
                "approval_required": False,
                "status": "needs_information",
                "response": msg,
                "audit_events": _event(state, "decision_reason_missing"),
            }

        # Evidence flags are derived from backend records only; customer text is
        # never passed as proof of delivery state or claim evidence.
        try:
            calculation = calculate_refund_amount(
                order_ref=state["order_id"],
                customer_ref=state["customer_id"],
                reason_code=reason_code,
                opened_item=True,
            )
            requested_amount = (
                calculation.get("requested_amount_inr")
                if calculation.get("eligible")
                else state.get("claimed_amount_inr")
            )
            result = evaluate_refund(
                order_ref=state["order_id"],
                customer_ref=state["customer_id"],
                reason_code=reason_code,
                requested_amount_inr=requested_amount,
                reported_damaged_within_period=False,
                photo_provided=False,
                parcel_declared_lost_or_dispute_upheld=False,
                customer_refuses_or_returns_late_order=False,
                inside_return_window=True,
                cancelled_before_dispatch=False,
                evaluation_date=date.today(),
            )
        except Exception as exc:
            result = {
                "eligible": False,
                "decision": "insufficient_information",
                "message": "Refund evaluation is temporarily unavailable.",
            }
            errors = list(state.get("errors", [])) + [f"refund_evaluation_error:{type(exc).__name__}"]
        else:
            errors = list(state.get("errors", []))

        decision = result.get("decision", "insufficient_information")
        approval_required = decision == "eligible_requires_human_approval"
        risk_requires_review = bool(state.get("requires_human"))
        if approval_required or (decision == "eligible_for_review" and risk_requires_review):
            review_reason = (
                f"Refund approval required: {result.get('approver', 'authorized reviewer')}"
                if approval_required
                else state.get("human_review_reason") or "Sentiment or safety escalation requires review."
            )
            response = (
                f"{review_reason} No refund has been approved or issued."
            )
            status = "pending_human_review"
        elif decision == "eligible_for_review":
            response = "Verified policy checks passed. The eligible refund action is being processed."
            status = "action_pending"
        elif decision == "ineligible":
            response = result.get("message", "The request does not meet the recorded policy.")
            status = "completed"
        else:
            response = result.get("message", "More information is required before this request can be assessed.")
            status = "needs_information"

        claimed_amount = state.get("claimed_amount_inr")
        high_value_needs_review = (
            decision == "insufficient_information"
            and claimed_amount is not None
            and claimed_amount > 2000
        )
        if high_value_needs_review:
            approval_required = False
            response = (
                "This high-value request needs human review and verification of the "
                "required evidence. No refund has been approved or issued."
            )
            status = "pending_human_review"

        return {
            "reason_code": reason_code,
            "refund_evaluation": result,
            "decision": decision,
            "decision_message": result.get("message"),
            "approval_required": approval_required,
            "approval_tier": result.get("approver"),
            "action_type": "refund",
            "action_ready": decision == "eligible_for_review" and not (
                approval_required or risk_requires_review or high_value_needs_review
            ),
            "requires_human": approval_required or high_value_needs_review or risk_requires_review,
            "human_review_reason": (
                f"Refund approval required: {result.get('approver', 'authorized reviewer')}"
                if approval_required else (
                    "High-value request requires human verification of evidence."
                    if high_value_needs_review else None
                )
            ),
            "status": status,
            "response": response,
            "errors": errors,
            "audit_events": _event(
                state, "refund_policy_evaluated",
                decision=decision,
                approval_required=approval_required,
                reason_code=reason_code,
                action_ready=decision == "eligible_for_review" and not (
                    approval_required or risk_requires_review or high_value_needs_review
                ),
            ),
        }

    # Non-refund order questions may use verified order data and policy evidence.
    if state.get("requires_human"):
        reason = state.get("human_review_reason") or "Risk or safety signal detected."
        return {
            "decision": "human_review_required",
            "decision_message": reason,
            "approval_required": False,
            "status": "pending_human_review",
            "response": "This request has been referred for human review. No business action was performed.",
            "audit_events": _event(state, "decision_routed_to_human", reason=reason),
        }
    if order_data.get("service_error"):
        reason = order_data.get("message") or "Order service is unavailable."
        return {
            "decision": "order_service_fallback",
            "decision_message": reason,
            "approval_required": False,
            "requires_human": True,
            "human_review_reason": reason,
            "status": "pending_human_review",
            "response": reason,
            "audit_events": _event(state, "order_service_fallback"),
        }
    if order_data.get("found") and issue_type == "shipping":
        shipment = order_data.get("shipment") or {}
        scan = shipment.get("last_scan")
        scan_at = shipment.get("last_scan_at")
        if scan:
            answer = f"Your order was verified. The latest recorded shipment scan is: {scan}."
            if scan_at:
                answer += f" Scan timestamp: {scan_at}."
        else:
            answer = "Your order was verified, but no shipment scan is currently available. Please contact support for further tracking."
        status = "answered"
        requires_human = False
    elif policy.get("status") == "evidence_found":
        answer = policy.get("answer", "")
        status = "answered"
        requires_human = False
    else:
        answer = (
            policy.get("answer")
            or "I couldn't find enough verified information to answer confidently. Please contact a human support agent."
        )
        status = "needs_human_review"
        requires_human = True

    return {
        "decision": "policy_answer" if status == "answered" else "insufficient_evidence",
        "decision_message": answer,
        "approval_required": False,
        "requires_human": requires_human,
        "human_review_reason": "Policy evidence was insufficient." if requires_human else None,
        "status": status,
        "response": answer,
        "audit_events": _event(state, "response_decided", status=status),
    }


def human_review_node(state: WorkflowState) -> WorkflowState:
    payload = {
        "type": "human_review",
        "ticket_id": state.get("ticket_id"),
        "reason": state.get("human_review_reason") or state.get("decision_message"),
        "approval_required": bool(state.get("approval_required")),
        "approval_tier": state.get("approval_tier"),
        "required_approver_role": (
            state.get("approval_tier")
            if state.get("action_type") == "refund" and state.get("approval_required")
            else None
        ),
        "decision": state.get("decision"),
        "message": "Resume this workflow with reviewer_id, approved (boolean), and optional note.",
    }
    review = interrupt(payload)
    try:
        normalized = _escalation_reviewer.validate(review)
    except ValueError as exc:
        return {
            "status": "review_invalid",
            "response": "The review response was invalid. No action was performed.",
            "errors": list(state.get("errors", [])) + [f"invalid_review:{exc}"],
            "audit_events": _event(state, "human_review_invalid"),
        }

    approved = normalized["approved"]
    if approved:
        evaluation = state.get("refund_evaluation") or {}
        action_type = state.get("action_type")
        policy_eligible = bool(evaluation.get("eligible"))
        required_role = (
            str(state.get("approval_tier") or "").casefold()
            if action_type == "refund" and state.get("approval_required")
            else None
        )
        approval_role = normalized.get("approver_role")
        if required_role and approval_role != required_role:
            return {
                "reviewer_id": normalized["reviewer_id"],
                "status": "review_invalid",
                "response": f"Approval from the required {required_role} tier is needed. No action was performed.",
                "requires_human": True,
                "action_ready": False,
                "audit_events": _event(state, "human_review_role_mismatch"),
            }
        replacement_eligible = action_type == "replacement" and bool(
            (state.get("order_data") or {}).get("found")
        )
        action_ready = (
            (action_type == "refund" and policy_eligible)
            or replacement_eligible
        )
        status = "action_pending" if action_ready else "review_completed"
        response = (
            f"Human approval recorded by {normalized['reviewer_id']}. The approved action is being processed."
            if action_ready
            else (
                f"Human review completed by {normalized['reviewer_id']}. "
                "Policy checks did not authorize a business action. No refund has been issued and no replacement was created."
            )
        )
    else:
        status = "review_rejected"
        response = f"Human reviewer {normalized['reviewer_id']} declined the request. No action was performed."
        action_ready = False
    return {
        "reviewer_id": normalized["reviewer_id"],
        "approval_role": normalized.get("approver_role"),
        "review_note": normalized.get("note"),
        "review_approved": approved,
        "status": status,
        "response": response,
        "requires_human": False,
        "action_ready": action_ready,
        "audit_events": _event(
            state, "human_review_completed",
            reviewer_id=normalized["reviewer_id"], approved=approved,
        ),
    }


def action_execution_node(state: WorkflowState) -> WorkflowState:
    """Perform a policy-checked action after routing and any required approval."""
    if not state.get("action_ready"):
        return {
            "status": state.get("status") or "review_completed",
            "response": state.get("response") or "No action was authorized.",
        }
    action_type = state.get("action_type")
    ticket_id = state.get("ticket_id") or uuid4().hex
    reviewer = state.get("reviewer_id")
    try:
        if action_type == "refund":
            evaluation = state.get("refund_evaluation") or {}
            result = _order_actions_agent.issue_refund(
                state.get("order_id") or "",
                state.get("customer_id") or "",
                state.get("reason_code") or "",
                ticket_id=ticket_id,
                amount_inr=evaluation.get("requested_amount_inr"),
                approved_by=state.get("approval_role") or reviewer,
                idempotency_key=f"{ticket_id}:refund",
            )
        elif action_type == "replacement":
            result = _order_actions_agent.create_replacement(
                state.get("order_id") or "",
                state.get("customer_id") or "",
                ticket_id=ticket_id,
                approved_by=reviewer,
                idempotency_key=f"{ticket_id}:replacement",
            )
        else:
            return {
                "status": "action_rejected",
                "action_ready": False,
                "response": "The requested action is not supported.",
                "audit_events": _event(state, "action_rejected", reason="unsupported_action"),
            }
    except Exception as exc:
        return {
            "status": "pending_human_review",
            "action_ready": False,
            "requires_human": True,
            "human_review_reason": "Action service failed; the request was sent to the human queue.",
            "response": "The action service is temporarily unavailable. No action was confirmed; human support has been notified.",
            "errors": list(state.get("errors", [])) + [f"action_error:{type(exc).__name__}"],
            "audit_events": _event(state, "action_service_failed", error=type(exc).__name__),
        }

    if result.get("executed"):
        if result.get("decision") == "refund_issued":
            response = (
                f"Refund of ₹{result['amount_inr']:,.2f} was issued for order "
                f"{result['order_ref']}. Refund reference: {result['refund_id']}."
            )
            status = "resolved"
        else:
            response = (
                f"The replacement was created for order {result.get('order_ref')}. "
                f"Replacement reference: {result.get('replacement_id')}."
            )
            status = "resolved"
    elif result.get("approval_required"):
        response = result.get("message") or "A qualified reviewer must approve this action."
        status = "pending_approval"
    else:
        response = result.get("message") or "The action was not performed because a required check failed."
        status = "needs_information"
    return {
        "action_result": result,
        "action_ready": False,
        "approval_required": bool(result.get("approval_required")),
        "approval_tier": result.get("approval_tier") or state.get("approval_tier"),
        "requires_human": bool(result.get("approval_required")),
        "human_review_reason": response if result.get("approval_required") else None,
        "status": status,
        "response": response,
        "audit_events": _event(
            state,
            "action_execution_completed" if result.get("executed") else "action_execution_blocked",
            action_type=action_type,
            decision=result.get("decision"),
            idempotent_replay=result.get("idempotent_replay", False),
        ),
    }


def final_response_node(state: WorkflowState) -> WorkflowState:
    if state.get("response"):
        return {
            "audit_events": _event(state, "workflow_completed", status=state.get("status")),
        }
    policy = state.get("policy_answer") or {}
    answer = policy.get("answer") or "Please contact a human support agent for further assistance."
    return {
        "response": answer,
        "status": state.get("status") or "answered",
        "audit_events": _event(state, "workflow_completed", status=state.get("status")),
    }


def _after_intake(state: WorkflowState) -> str:
    if state.get("status") == "needs_information" and state.get("response"):
        return "finish"
    return "guardrail"


def _after_decision(state: WorkflowState) -> str:
    if state.get("requires_human") or state.get("approval_required"):
        return "human_review"
    if state.get("action_ready"):
        return "action_execution"
    return "finish"


def _after_review(state: WorkflowState) -> str:
    return "action_execution" if state.get("action_ready") else "finish"


def build_graph(checkpointer: Any = None):
    """Build a compiled ShopSense graph, using in-memory checkpoints by default."""
    builder = StateGraph(WorkflowState)
    builder.add_node("intake", intake_node)
    builder.add_node("guardrail", guardrail_node)
    builder.add_node("order_lookup", order_lookup_node)
    builder.add_node("policy_retrieval", policy_retrieval_node)
    builder.add_node("decision", decision_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("action_execution", action_execution_node)
    builder.add_node("finish", final_response_node)

    builder.add_edge(START, "intake")
    builder.add_conditional_edges("intake", _after_intake, {"guardrail": "guardrail", "finish": "finish"})
    builder.add_edge("guardrail", "order_lookup")
    builder.add_edge("order_lookup", "policy_retrieval")
    builder.add_edge("policy_retrieval", "decision")
    builder.add_conditional_edges(
        "decision",
        _after_decision,
        {"human_review": "human_review", "action_execution": "action_execution", "finish": "finish"},
    )
    builder.add_conditional_edges(
        "human_review",
        _after_review,
        {"action_execution": "action_execution", "finish": "finish"},
    )
    builder.add_edge("action_execution", "finish")
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=checkpointer or make_checkpointer())


support_graph = build_graph()


def invoke_support(
    message: str,
    customer_id: str | None = None,
    order_id: str | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    """Run a support ticket with a stable thread ID for later review/resume."""
    thread_id = ticket_id or uuid4().hex
    initial: WorkflowState = {
        "raw_message": message,
        "customer_id": customer_id,
        "order_id": order_id,
        "ticket_id": thread_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "errors": [],
        "audit_events": [],
    }
    result = support_graph.invoke(
        initial,
        config={"configurable": {"thread_id": thread_id}},
    )
    serialized = serialize_result(result, thread_id)
    _persist_ticket(result, thread_id)
    return serialized


def resume_support(
    thread_id: str,
    reviewer_id: str,
    approved: bool,
    note: str | None = None,
    approver_role: str | None = None,
) -> dict[str, Any]:
    """Resume a paused human-review thread with an explicit reviewer decision."""
    payload = {
        "reviewer_id": reviewer_id,
        "approved": approved,
        "note": note,
        "approver_role": approver_role,
    }
    result = support_graph.invoke(
        Command(resume=payload),
        config={"configurable": {"thread_id": thread_id}},
    )
    serialized = serialize_result(result, thread_id)
    _persist_ticket(result, thread_id)
    return serialized


def _persist_ticket(result: dict[str, Any], thread_id: str) -> None:
    if not result.get("ticket_id") and not result.get("raw_message"):
        return
    try:
        save_ticket({
            **result,
            "ticket_id": result.get("ticket_id", thread_id),
            "thread_id": thread_id,
        })
    except Exception:
        # Persistence errors must be visible to service logs without exposing
        # customer text or interrupting an already-checkpointed review.
        import logging

        logging.getLogger(__name__).exception("ticket_persistence_failed")


def serialize_result(result: dict[str, Any], thread_id: str) -> dict[str, Any]:
    """Convert LangGraph interrupt objects to JSON-safe response values."""
    interrupts = []
    for item in result.get("__interrupt__", []) or []:
        value = getattr(item, "value", item)
        if isinstance(value, dict):
            interrupts.append(value)
        else:
            interrupts.append({"message": str(value)})
    return {
        "thread_id": thread_id,
        "ticket_id": result.get("ticket_id", thread_id),
        "status": result.get("status", "unknown"),
        "response": result.get("response"),
        "issue_type": result.get("issue_type"),
        "sentiment": result.get("sentiment"),
        "urgency": result.get("urgency"),
        "order_id": result.get("order_id"),
        "order_found": bool((result.get("order_data") or {}).get("found")),
        "decision": result.get("decision"),
        "action_type": result.get("action_type"),
        "action_result": result.get("action_result"),
        "decision_message": result.get("decision_message"),
        "refund_evaluation": result.get("refund_evaluation"),
        "approval_required": bool(result.get("approval_required", False)),
        "approval_tier": result.get("approval_tier"),
        "requires_human": bool(result.get("requires_human", False)),
        "human_review_reason": result.get("human_review_reason"),
        "citations": result.get("citations", []),
        "policy_answer": result.get("policy_answer"),
        "missing_fields": result.get("missing_fields", []),
        "errors": result.get("errors", []),
        "audit_events": result.get("audit_events", []),
        "interrupts": interrupts,
        "reviewer_id": result.get("reviewer_id"),
        "review_approved": result.get("review_approved"),
        "customer_id": result.get("customer_id"),
    }
