
from datetime import date

from capstone.tools.actions import evaluate_refund


ORDER_REF = "KW-O-000000"
CUSTOMER_REF = "KW-C-00317"
TEST_DATE = date(2026, 7, 20)


def test_large_refund_requires_human_review():
    result = evaluate_refund(
        ORDER_REF,
        CUSTOMER_REF,
        "damaged",
        reported_damaged_within_period=True,
        photo_provided=True,
        evaluation_date=TEST_DATE,
    )

    assert result["eligible"] is True
    assert result["requested_amount_inr"] == 12999.0
    assert result["approver"] == "ops_manager"
    assert result["decision"] == "eligible_requires_human_approval"


def test_small_refund_is_routed_to_automated_review():
    result = evaluate_refund(
        ORDER_REF,
        CUSTOMER_REF,
        "damaged",
        requested_amount_inr=1000,
        reported_damaged_within_period=True,
        photo_provided=True,
        evaluation_date=TEST_DATE,
    )

    assert result["eligible"] is True
    assert result["approver"] == "auto"
    assert result["decision"] == "eligible_for_review"


def test_damaged_claim_without_photo_needs_more_information():
    result = evaluate_refund(
        ORDER_REF,
        CUSTOMER_REF,
        "damaged",
        reported_damaged_within_period=True,
        photo_provided=False,
        evaluation_date=TEST_DATE,
    )

    assert result["eligible"] is False
    assert result["decision"] == "insufficient_information"


def test_wrong_customer_cannot_evaluate_order_refund():
    result = evaluate_refund(
        ORDER_REF,
        "KW-C-00001",
        "damaged",
        reported_damaged_within_period=True,
        photo_provided=True,
        evaluation_date=TEST_DATE,
    )

    assert result["eligible"] is False
    assert result["decision"] == "insufficient_information"
    assert "order_value_inr" not in result


def test_refund_cannot_exceed_order_value():
    result = evaluate_refund(
        ORDER_REF,
        CUSTOMER_REF,
        "damaged",
        requested_amount_inr=20000,
        reported_damaged_within_period=True,
        photo_provided=True,
        evaluation_date=TEST_DATE,
    )

    assert result["eligible"] is False
    assert result["decision"] == "ineligible"


def test_late_delivery_requires_customer_to_refuse_or_return_order():
    result = evaluate_refund(
        ORDER_REF,
        CUSTOMER_REF,
        "late_delivery",
        customer_refuses_or_returns_late_order=False,
        evaluation_date=TEST_DATE,
    )

    assert result["eligible"] is False
    assert result["decision"] == "insufficient_information"


def test_expired_defect_claim_is_rejected():
    result = evaluate_refund(
        ORDER_REF,
        CUSTOMER_REF,
        "damaged",
        reported_damaged_within_period=True,
        photo_provided=True,
        evaluation_date=date(2026, 10, 10),
    )

    assert result["eligible"] is False
    assert result["decision"] == "ineligible"


def test_expired_changed_mind_return_is_rejected_before_confirmation():
    result = evaluate_refund(
        ORDER_REF,
        CUSTOMER_REF,
        "changed_mind",
        inside_return_window=False,
        evaluation_date=date(2026, 10, 10),
    )

    assert result["eligible"] is False
    assert result["decision"] == "ineligible"
    assert "return-by date has passed" in result["message"].lower()
