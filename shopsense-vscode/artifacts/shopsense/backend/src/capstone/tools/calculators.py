"""Deterministic financial calculations for ShopSense policy decisions."""

from typing import Any


def calculate_net_refund(
    order_value_inr: float,
    *,
    restocking_fee_pct: float = 0,
    pickup_fee_inr: float = 0,
) -> dict[str, Any]:
    """Calculate a potential net refund; this function never executes payment."""
    value = float(order_value_inr)
    percent = float(restocking_fee_pct)
    pickup = float(pickup_fee_inr)

    if value < 0:
        raise ValueError("order_value_inr must be non-negative")
    if not 0 <= percent <= 100:
        raise ValueError("restocking_fee_pct must be between 0 and 100")
    if pickup < 0:
        raise ValueError("pickup_fee_inr must be non-negative")

    restocking_fee = round(value * percent / 100, 2)
    net = round(max(0.0, value - restocking_fee - pickup), 2)
    return {
        "order_value_inr": round(value, 2),
        "restocking_fee_pct": percent,
        "restocking_fee_inr": restocking_fee,
        "pickup_fee_inr": round(pickup, 2),
        "potential_net_refund_inr": net,
        "executed": False,
    }
