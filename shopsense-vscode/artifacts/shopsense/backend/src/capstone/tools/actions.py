
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from capstone.storage import database, initialize_store

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "shopsense" / "mock_api"


def _load_table(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Policy data file not found: {path}")
    return pd.read_csv(path)


def _result(
    decision: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    eligible_decisions = {
        "eligible_for_review",
        "eligible_requires_human_approval",
    }
    return {
        "eligible": decision in eligible_decisions,
        "decision": decision,
        "message": message,
        **extra,
    }


def calculate_refund_amount(
    order_ref: str,
    customer_ref: str,
    reason_code: str,
    *,
    opened_item: bool = True,
) -> dict[str, Any]:
    """Calculate net refund and approval tier from verified order/category data."""
    from capstone.tools.repository import lookup_order

    verified = lookup_order(order_ref, customer_ref)
    if not verified.get("found"):
        return {"eligible": False, "decision": "insufficient_information", "message": verified.get("message")}
    order = verified["order"]
    product = verified.get("product") or {}
    category = str(product.get("category") or "")
    return calculate_refund_for_category(
        category,
        float(order["order_value_inr"]),
        reason_code,
        opened_item=opened_item,
    )


def calculate_refund_for_category(
    category: str,
    order_value_inr: float,
    reason_code: str,
    *,
    opened_item: bool,
) -> dict[str, Any]:
    """Calculate a non-mutating policy estimate from a requested category/value."""
    if order_value_inr <= 0:
        return {"eligible": False, "decision": "invalid_amount", "message": "Order value must be greater than zero."}
    rules = _load_table("refund_rules")
    rule_rows = rules[rules["reason_code"].astype(str).str.lower() == reason_code.strip().lower()]
    policy_rows = _load_table("category_policies")
    policy_rows = policy_rows[policy_rows["category"].astype(str).str.casefold() == category.casefold()]
    if rule_rows.empty or policy_rows.empty:
        return {"eligible": False, "decision": "insufficient_information", "message": "A matching refund rule and category policy are required."}

    rule = rule_rows.iloc[0]
    policy = policy_rows.iloc[0]
    gross = float(order_value_inr) * float(rule["refund_pct"]) / 100
    restocking_fee = 0.0
    if opened_item and str(rule["restocking_fee_applies"]).strip().lower() in {"true", "1"}:
        restocking_fee = gross * float(policy["restocking_fee_pct"]) / 100
    pickup_fee = 0.0
    if str(rule["return_shipping_paid_by"]).strip().lower() == "customer":
        pickup_fee = float(policy["return_pickup_fee_inr"])
    net = max(0.0, round(gross - restocking_fee - pickup_fee, 2))
    authority = _load_table("refund_authority")
    auto_rows = authority[authority["approver"].astype(str).str.lower() == "auto"]
    auto_cap = float(auto_rows.iloc[0]["max_refund_inr"]) if not auto_rows.empty else 0.0
    human_rows = authority[authority["is_human"].astype(str).str.lower() == "true"].dropna(subset=["max_refund_inr"])
    human_rows = human_rows.sort_values("max_refund_inr")
    approver = "auto" if net <= auto_cap else "finance"
    tier = "Tier 1" if net <= auto_cap else "Tier 3"
    approver_options = ["agent", "auto"] if net <= auto_cap else []
    if net > auto_cap:
        matching = human_rows[human_rows["max_refund_inr"].astype(float) >= net]
        if not matching.empty:
            approver = str(matching.iloc[0]["approver"])
            tier = "Tier 2" if net <= 10000 else "Tier 3"
            approver_options = [approver]
    return {
        "eligible": True,
        "decision": "eligible_for_review" if net <= auto_cap else "eligible_requires_human_approval",
        "category": category,
        "order_value_inr": round(float(order_value_inr), 2),
        "gross_refund_inr": round(gross, 2),
        "restocking_fee_inr": round(restocking_fee, 2),
        "pickup_fee_inr": round(pickup_fee, 2),
        "requested_amount_inr": net,
        "approval_tier": approver,
        "approval_tier_label": tier,
        "authorized_approvers": approver_options,
        "return_required": str(rule["return_required"]).strip().lower() in {"true", "1"},
        "reason_code": reason_code,
    }


def _human_approval_valid(amount: float, approver: str | None) -> bool:
    if not approver or approver.strip().lower() in {"auto", "bot", "assistant"}:
        return False
    authority = _load_table("refund_authority")
    human_rows = authority[authority["is_human"].astype(str).str.lower() == "true"]
    normalized = approver.strip().casefold()
    matching = human_rows[
        (human_rows["approver"].astype(str).str.casefold() == normalized)
        | (human_rows["role"].astype(str).str.casefold() == normalized)
    ]
    if matching.empty:
        return False
    limit = matching.iloc[0]["max_refund_inr"]
    return pd.isna(limit) or float(limit) >= amount


def calculate_delay_compensation(
    service_tier: str,
    delivery_zone: str,
    days_since_order: int,
) -> dict[str, Any]:
    """Calculate verified delivery promise and goodwill credit bands."""
    if days_since_order < 0:
        return {"eligible": False, "decision": "invalid_duration"}
    services = _load_table("delivery_services")
    promise_rows = services[
        (services["service_tier"].astype(str).str.casefold() == service_tier.strip().casefold())
        & (services["delivery_zone"].astype(str).str.casefold() == delivery_zone.strip().casefold())
    ]
    if promise_rows.empty:
        return {"eligible": False, "decision": "insufficient_information", "message": "The delivery promise could not be verified."}
    promise_days = int(promise_rows.iloc[0]["promise_days"])
    days_late = max(0, days_since_order - promise_days)
    bands = _load_table("delay_compensation")
    credit = 0
    for _, band in bands.iterrows():
        minimum = int(band["min_days_late"])
        maximum = None if pd.isna(band["max_days_late"]) else int(band["max_days_late"])
        if days_late >= minimum and (maximum is None or days_late <= maximum):
            credit = int(band["goodwill_credit_inr"])
            break
    return {
        "eligible": True,
        "service_tier": service_tier.strip().lower(),
        "delivery_zone": delivery_zone.strip().lower(),
        "promise_days": promise_days,
        "days_since_order": days_since_order,
        "days_late": days_late,
        "goodwill_credit_inr": credit,
        "currency": "INR",
    }


def _previous_action(db, idempotency_key: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT action_type, result_json FROM action_executions WHERE idempotency_key = ?",
        (idempotency_key,),
    ).fetchone()
    if not row:
        return None
    result = json.loads(row["result_json"])
    result.setdefault("action_type", row["action_type"])
    return result


def execute_refund(
    order_ref: str,
    customer_ref: str,
    reason_code: str,
    *,
    ticket_id: str,
    amount_inr: float | None = None,
    approved_by: str | None = None,
    opened_item: bool = True,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Execute a guarded mock refund with an atomic idempotency key."""
    from capstone.tools.repository import lookup_order

    if not idempotency_key or not idempotency_key.strip() or not ticket_id or not ticket_id.strip():
        return {"executed": False, "decision": "invalid_request", "message": "A ticket ID and idempotency key are required."}
    initialize_store()
    with database() as db:
        previous = _previous_action(db, idempotency_key.strip())
    if previous:
        if previous.get("action_type") != "refund":
            return {"executed": False, "decision": "idempotency_key_conflict", "message": "The idempotency key was used for a different action."}
        previous["idempotent_replay"] = True
        return previous
    verified = lookup_order(order_ref, customer_ref)
    if not verified.get("found"):
        return {"executed": False, "decision": "ownership_or_lookup_failed", "message": verified.get("message")}
    calculation = calculate_refund_amount(order_ref, customer_ref, reason_code, opened_item=opened_item)
    if not calculation.get("eligible"):
        return {"executed": False, **calculation}
    amount = round(float(amount_inr if amount_inr is not None else calculation["requested_amount_inr"]), 2)
    order_value = float(calculation["order_value_inr"])
    if amount <= 0 or amount > order_value or amount > float(calculation["requested_amount_inr"]):
        return {"executed": False, "decision": "amount_out_of_policy", "message": "The amount exceeds the verified net refund value."}
    shipment = verified.get("shipment") or {}
    order_status = str(verified["order"].get("status", "")).casefold()
    scan_text = str(shipment.get("last_scan", "")).casefold()
    fulfilment = verified.get("fulfilment") or {}
    policy_check = evaluate_refund(
        order_ref=order_ref,
        customer_ref=customer_ref,
        reason_code=reason_code,
        requested_amount_inr=amount,
        parcel_declared_lost_or_dispute_upheld=(
            "lost" in order_status or "lost" in scan_text
        ),
        cancelled_before_dispatch=(
            "cancel" in order_status
            and "dispatch" not in order_status
            and not shipment.get("tracking_id")
        ),
        evaluation_date=date.today(),
    )
    if not policy_check.get("eligible"):
        return {
            "executed": False,
            "decision": policy_check.get("decision", "policy_check_failed"),
            "message": policy_check.get("message", "A required policy check did not pass."),
        }

    auto_rows = _load_table("refund_authority")
    auto_rows = auto_rows[auto_rows["approver"].astype(str).str.lower() == "auto"]
    auto_cap = float(auto_rows.iloc[0]["max_refund_inr"]) if not auto_rows.empty else 0.0
    if amount > auto_cap and not _human_approval_valid(amount, approved_by):
        return {
            "executed": False,
            "decision": "approval_required",
            "approval_required": True,
            "approval_tier": calculation["approval_tier"],
            "amount_inr": amount,
            "message": "A qualified human approval is required before this refund can execute.",
        }

    initialize_store()
    now = datetime.now(timezone.utc).isoformat()
    refund_id = f"KW-RF-{uuid4().hex[:12].upper()}"
    result = {
        "executed": True,
        "action_type": "refund",
        "decision": "refund_issued",
        "refund_id": refund_id,
        "order_ref": order_ref.strip().upper(),
        "amount_inr": amount,
        "approved_by": (approved_by or "auto").strip(),
        "status": "processed",
        "idempotent_replay": False,
    }
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = _previous_action(db, idempotency_key)
        if previous:
            if previous.get("action_type") != "refund":
                return {"executed": False, "decision": "idempotency_key_conflict", "message": "The idempotency key was used for a different action."}
            previous["idempotent_replay"] = True
            return previous
        payload = json.dumps(result, ensure_ascii=False)
        db.execute(
            "INSERT INTO refunds(refund_id,order_ref,amount_inr,reason_code,status,approved_by,requested_on,payload_json) VALUES(?,?,?,?,?,?,?,?)",
            (refund_id, order_ref.strip().upper(), amount, reason_code.strip().lower(), "processed", approved_by or "auto", now[:10], payload),
        )
        db.execute(
            "INSERT INTO action_executions(idempotency_key,ticket_id,action_type,status,result_json,created_at) VALUES(?,?,?,?,?,?)",
            (idempotency_key.strip(), ticket_id.strip(), "refund", "completed", payload, now),
        )
    return result


def execute_replacement(
    order_ref: str,
    customer_ref: str,
    *,
    ticket_id: str,
    approved_by: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a replacement only for the verified customer and approved value tier."""
    from capstone.tools.repository import lookup_order

    if not idempotency_key or not idempotency_key.strip() or not ticket_id or not ticket_id.strip():
        return {"executed": False, "decision": "invalid_request", "message": "A ticket ID and idempotency key are required."}
    initialize_store()
    with database() as db:
        previous = _previous_action(db, idempotency_key.strip())
    if previous:
        if previous.get("action_type") != "replacement":
            return {"executed": False, "decision": "idempotency_key_conflict", "message": "The idempotency key was used for a different action."}
        previous["idempotent_replay"] = True
        return previous
    verified = lookup_order(order_ref, customer_ref)
    if not verified.get("found"):
        return {"executed": False, "decision": "ownership_or_lookup_failed", "message": verified.get("message")}
    product = verified.get("product") or {}
    if not bool(product.get("in_stock")):
        return {"executed": False, "decision": "out_of_stock", "message": "The replacement cannot be created because stock is not confirmed."}
    order_value = float(verified["order"]["order_value_inr"])
    authority = _load_table("refund_authority")
    auto_rows = authority[authority["approver"].astype(str).str.lower() == "auto"]
    auto_cap = float(auto_rows.iloc[0]["max_refund_inr"]) if not auto_rows.empty else 0.0
    if order_value > auto_cap and not _human_approval_valid(order_value, approved_by):
        return {"executed": False, "decision": "approval_required", "approval_required": True, "amount_inr": order_value}
    initialize_store()
    now = datetime.now(timezone.utc).isoformat()
    replacement_id = f"KW-RP-{uuid4().hex[:12].upper()}"
    result = {
        "executed": True, "action_type": "replacement", "decision": "replacement_created", "replacement_id": replacement_id,
        "order_ref": order_ref.strip().upper(), "approved_by": (approved_by or "auto").strip(),
        "status": "created", "idempotent_replay": False,
    }
    payload = json.dumps(result, ensure_ascii=False)
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = _previous_action(db, idempotency_key)
        if previous:
            if previous.get("action_type") != "replacement":
                return {"executed": False, "decision": "idempotency_key_conflict", "message": "The idempotency key was used for a different action."}
            previous["idempotent_replay"] = True
            return previous
        db.execute(
            "INSERT INTO replacements(replacement_id,order_ref,status,approved_by,created_at,payload_json) VALUES(?,?,?,?,?,?)",
            (replacement_id, order_ref.strip().upper(), "created", approved_by or "auto", now, payload),
        )
        db.execute(
            "INSERT INTO action_executions(idempotency_key,ticket_id,action_type,status,result_json,created_at) VALUES(?,?,?,?,?,?)",
            (idempotency_key.strip(), ticket_id.strip(), "replacement", "completed", payload, now),
        )
    return result


def evaluate_refund(
    order_ref: str,
    customer_ref: str,
    reason_code: str,
    requested_amount_inr: float | None = None,
    *,
    reported_damaged_within_period: bool = False,
    photo_provided: bool = False,
    parcel_declared_lost_or_dispute_upheld: bool = False,
    customer_refuses_or_returns_late_order: bool = False,
    inside_return_window: bool = False,
    cancelled_before_dispatch: bool = False,
    evaluation_date: date | None = None,
) -> dict[str, Any]:
    """Evaluate refund policy and recommend approval routing. Never issues refunds."""

    from capstone.tools.repository import lookup_order

    reason_code = reason_code.strip().lower()
    today = evaluation_date or date.today()

    order_result = lookup_order(order_ref, customer_ref)
    if not order_result["found"]:
        return _result(
            "insufficient_information",
            "The order could not be verified for this customer.",
        )

    order = order_result["order"]
    order_value = float(order["order_value_inr"])

    rules = _load_table("refund_rules")
    rule_rows = rules[
        rules["reason_code"].astype(str).str.lower() == reason_code
    ]
    if rule_rows.empty:
        return _result(
            "insufficient_information",
            f"Unknown refund reason: {reason_code}",
        )

    rule = rule_rows.iloc[0]

    # Resolve the product and its category-specific policy from the verified order lookup.
    product = order_result.get("product") or {}
    if not product:
        return _result(
            "insufficient_information",
            "Product category could not be verified.",
        )

    category = str(product["category"])
    policies = _load_table("category_policies")
    policy_rows = policies[
        policies["category"].astype(str).str.casefold() == category.casefold()
    ]
    if policy_rows.empty:
        return _result(
            "insufficient_information",
            "No category-specific policy was found.",
        )

    policy = policy_rows.iloc[0]
    fulfilment = order_result.get("fulfilment") or {}

    placed_at = pd.to_datetime(order.get("placed_at"), errors="coerce")
    delivered_on = pd.to_datetime(
        fulfilment.get("delivered_on"), errors="coerce"
    )

    # Prefer delivery date for defect claims; otherwise use order date.
    reference_date = (
        delivered_on if not pd.isna(delivered_on) else placed_at
    )
    elapsed_days = None
    if not pd.isna(reference_date):
        elapsed_days = (
            pd.Timestamp(today).normalize() - reference_date.normalize()
        ).days

    return_by = pd.to_datetime(
        fulfilment.get("return_by"), errors="coerce"
    )

    # Validate required evidence before making a deadline decision.
    if reason_code == "damaged":
        if not (reported_damaged_within_period and photo_provided):
            return _result(
                "insufficient_information",
                "A timely report and photo are required for a damaged-item claim.",
            )

        defect_days = int(policy["defect_claim_days"])
        if elapsed_days is None:
            return _result(
                "insufficient_information",
                "The delivery date could not be verified for the defect claim.",
            )
        if elapsed_days < 0:
            return _result(
                "insufficient_information",
                "The delivery date is in the future; the claim date needs verification.",
            )
        if elapsed_days > defect_days:
            return _result(
                "ineligible",
                "The category-specific defect-claim period has passed.",
                order_ref=order_ref,
                category=category,
            )

    elif reason_code == "not_delivered":
        if not parcel_declared_lost_or_dispute_upheld:
            return _result(
                "insufficient_information",
                "Confirm the parcel was declared lost or the delivery dispute was upheld.",
            )

    elif reason_code == "late_delivery":
        if not customer_refuses_or_returns_late_order:
            return _result(
                "insufficient_information",
                "A customer keeping a late order receives a delay credit instead of a full refund.",
            )

    elif reason_code == "cancelled_before_dispatch":
        if not cancelled_before_dispatch:
            return _result(
                "insufficient_information",
                "Confirm the order was cancelled before dispatch.",
            )

    # Check return deadline for reasons subject to the return window.
    if reason_code in {"changed_mind", "late_delivery", "wrong_item", "quality"}:
        if not pd.isna(return_by):
            if pd.Timestamp(today).normalize() > return_by.normalize():
                return _result(
                    "ineligible",
                    "The recorded return-by date has passed.",
                    order_ref=order_ref,
                    category=category,
                    return_by=str(return_by.date()),
                )
        elif elapsed_days is not None:
            if elapsed_days < 0:
                return _result(
                    "insufficient_information",
                    "The order date is in the future; please verify the order.",
                )
            if elapsed_days > int(policy["return_window_days"]):
                return _result(
                    "ineligible",
                    "The category-specific return window has passed.",
                    order_ref=order_ref,
                    category=category,
                )
        else:
            return _result(
                "insufficient_information",
                "The order date could not be verified.",
            )

    # The verified date, not a caller-supplied boolean, establishes return-window eligibility.

    # Verify the requested amount.
    amount = (
        order_value * float(rule["refund_pct"]) / 100
        if requested_amount_inr is None
        else float(requested_amount_inr)
    )

    if not pd.notna(amount) or amount <= 0 or amount > order_value:
        return _result(
            "ineligible",
            "The requested amount must be greater than ₹0 and no more than the order value.",
        )

    # Recommend an approver based on the configured authority table.
    authority = _load_table("refund_authority")
    auto_rows = authority[authority["approver"] == "auto"]
    if auto_rows.empty or pd.isna(auto_rows.iloc[0]["max_refund_inr"]):
        return _result(
            "insufficient_information",
            "Automated approval limits are not configured.",
        )

    auto_cap = float(auto_rows.iloc[0]["max_refund_inr"])
    human_limits = authority[
        authority["is_human"].astype(str).str.lower() == "true"
    ].dropna(subset=["max_refund_inr"])
    human_limits = human_limits.sort_values("max_refund_inr")

    if amount <= auto_cap:
        approver = "auto"
        decision = "eligible_for_review"
    else:
        matching_approvers = human_limits[
            human_limits["max_refund_inr"].astype(float) >= amount
        ]
        if matching_approvers.empty:
            approver = "finance"
        else:
            approver = str(matching_approvers.iloc[0]["approver"])
        decision = "eligible_requires_human_approval"

    return _result(
        decision,
        "Preliminary policy checks passed. No refund has been approved or issued.",
        order_ref=order_ref,
        reason_code=reason_code,
        category=category,
        order_value_inr=order_value,
        requested_amount_inr=round(amount, 2),
        approver=approver,
        return_required=bool(rule["return_required"]),
        restocking_fee_applies=bool(rule["restocking_fee_applies"]),
        return_shipping_paid_by=str(rule["return_shipping_paid_by"]),
    )
