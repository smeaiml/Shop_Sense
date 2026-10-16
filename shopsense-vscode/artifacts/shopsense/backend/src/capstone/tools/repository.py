"""Customer-scoped access to persistent mock commerce data."""

from __future__ import annotations

import logging
from threading import Lock
from time import sleep
from typing import Any

import pandas as pd

from capstone.reliability.circuit_breaker import CircuitBreaker, CircuitOpenError
from capstone.settings import DATA_DIR
from capstone.storage import TABLES, get_customer, get_order_records

logger = logging.getLogger(__name__)
_order_breaker = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=15)
_failure_lock = Lock()
_injected_failures = 0


def _load_table(name: str) -> pd.DataFrame:
    """Load a whitelisted mock fixture for non-sensitive catalog lookups."""
    if name not in TABLES:
        raise ValueError("Unknown ShopSense mock data table.")
    path = DATA_DIR / "mock_api" / f"{name}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"ShopSense mock data table is missing: {name}")
    return pd.read_csv(path)


def inject_order_failures(count: int) -> None:
    """Test/demo hook for deterministic upstream-failure exercises."""
    if count < 0 or count > 100:
        raise ValueError("Failure count must be between 0 and 100.")
    global _injected_failures
    with _failure_lock:
        _injected_failures = count


def reset_order_reliability() -> None:
    global _injected_failures
    with _failure_lock:
        _injected_failures = 0
        _order_breaker.failures = 0
        _order_breaker.opened_at = None


def _load_owned_order(order_ref: str, customer_ref: str) -> dict[str, Any] | None:
    global _injected_failures
    with _failure_lock:
        if _injected_failures:
            _injected_failures -= 1
            raise TimeoutError("Injected order-service failure.")
    return get_order_records(order_ref, customer_ref)


def lookup_order(order_ref: str, customer_ref: str | None = None) -> dict[str, Any]:
    """Return order data only when both identifiers are present and ownership matches."""
    normalized_order = (order_ref or "").strip().upper()
    normalized_customer = (customer_ref or "").strip().upper()
    if not normalized_order:
        return {"found": False, "message": "Please provide an order reference."}
    if not normalized_customer:
        return {
            "found": False,
            "message": "A verified customer reference is required for order lookup.",
            "ownership_required": True,
        }

    for attempt in range(2):
        try:
            data = _order_breaker.call(_load_owned_order, normalized_order, normalized_customer)
            if data is None:
                return {"found": False, "message": "Order not found for this customer."}
            order = data["order"]
            return {
                "found": True,
                "order": order,
                "product": data.get("product"),
                "category": data.get("category"),
                "shipment": data.get("shipment"),
                "refunds": data.get("refunds", []),
                "fulfilment": data.get("fulfilment"),
            }
        except CircuitOpenError:
            logger.warning("order_service_circuit_open")
            break
        except Exception as exc:
            logger.warning(
                "order_lookup_attempt_failed",
                extra={"attempt": attempt + 1, "error_type": type(exc).__name__},
            )
            if attempt == 0:
                sleep(0.025)

    return {
        "found": False,
        "message": "The order service is temporarily unavailable. The request was sent to the human support queue.",
        "service_error": True,
        "requires_human": True,
    }


def lookup_customer(customer_ref: str) -> dict[str, Any] | None:
    if not customer_ref or not customer_ref.strip():
        return None
    return get_customer(customer_ref.strip().upper())
