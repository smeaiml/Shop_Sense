"""Order-action specialist; all mutations go through guarded business tools."""

from typing import Any

from capstone.tools.actions import (
    calculate_refund_amount,
    evaluate_refund,
    execute_refund,
    execute_replacement,
)
from capstone.tools.repository import lookup_order


class OrderActionsAgent:
    @staticmethod
    def lookup(order_ref: str, customer_ref: str) -> dict[str, Any]:
        return lookup_order(order_ref, customer_ref)

    @staticmethod
    def track_shipping(order_ref: str, customer_ref: str) -> dict[str, Any]:
        result = lookup_order(order_ref, customer_ref)
        if not result.get("found"):
            return result
        return {
            "found": True,
            "order_ref": order_ref.strip().upper(),
            "shipment": result.get("shipment"),
            "fulfilment": result.get("fulfilment"),
        }

    @staticmethod
    def calculate_refund(*args, **kwargs):
        return calculate_refund_amount(*args, **kwargs)

    @staticmethod
    def evaluate_refund(*args, **kwargs):
        return evaluate_refund(*args, **kwargs)

    @staticmethod
    def issue_refund(*args, **kwargs):
        return execute_refund(*args, **kwargs)

    @staticmethod
    def create_replacement(*args, **kwargs):
        return execute_replacement(*args, **kwargs)
