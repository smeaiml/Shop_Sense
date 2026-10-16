
from capstone.tools.repository import lookup_order


def test_existing_order_is_found():
    result = lookup_order("KW-O-000000", "KW-C-00317")

    assert result["found"] is True
    assert result["order"]["order_ref"] == "KW-O-000000"


def test_correct_customer_can_access_order():
    result = lookup_order("KW-O-000000", "KW-C-00317")

    assert result["found"] is True
    assert result["order"]["customer_ref"] == "KW-C-00317"


def test_wrong_customer_cannot_access_order():
    result = lookup_order("KW-O-000000", "KW-C-00001")

    assert result["found"] is False
    assert "order" not in result
    assert "refunds" not in result


def test_nonexistent_order_is_not_found():
    result = lookup_order("INVALID-ORDER", "KW-C-00317")

    assert result["found"] is False


def test_order_includes_related_data_fields():
    result = lookup_order("KW-O-000000", "KW-C-00317")

    assert "shipment" in result
    assert "refunds" in result
    assert "fulfilment" in result
    assert result["shipment"]["tracking_id"] == "KW-TRK-0000000"
