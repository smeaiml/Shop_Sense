"""MCP server exposing the same guarded ShopSense business tools as the API."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from capstone.tools.actions import calculate_refund_amount, execute_refund, execute_replacement
from capstone.tools.repository import lookup_order

mcp = FastMCP("ShopSense commerce tools")


@mcp.tool()
def order_lookup(order_ref: str, customer_ref: str) -> dict[str, Any]:
    """Look up an order only when its customer reference matches."""
    return lookup_order(order_ref, customer_ref)


@mcp.tool()
def shipping_tracker(order_ref: str, customer_ref: str) -> dict[str, Any]:
    """Return the latest shipment scan for the verified customer-owned order."""
    result = lookup_order(order_ref, customer_ref)
    if not result.get("found"):
        return result
    return {
        "found": True,
        "order_ref": order_ref.strip().upper(),
        "shipment": result.get("shipment"),
        "fulfilment": result.get("fulfilment"),
    }


@mcp.tool()
def refund_calculator(
    order_ref: str,
    customer_ref: str,
    reason_code: str,
    opened_item: bool = True,
) -> dict[str, Any]:
    """Calculate the refund after validating ownership, category fees, and approval tier."""
    return calculate_refund_amount(
        order_ref, customer_ref, reason_code, opened_item=opened_item
    )


@mcp.tool()
def refund_issue(
    order_ref: str,
    customer_ref: str,
    reason_code: str,
    ticket_id: str,
    idempotency_key: str,
    amount_inr: float | None = None,
) -> dict[str, Any]:
    """Issue a verified mock refund; amounts over the tool cap are blocked for human review."""
    return execute_refund(
        order_ref,
        customer_ref,
        reason_code,
        ticket_id=ticket_id,
        amount_inr=amount_inr,
        idempotency_key=idempotency_key,
    )


@mcp.tool()
def replacement_create(
    order_ref: str,
    customer_ref: str,
    ticket_id: str,
    idempotency_key: str,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Create a customer-scoped replacement with stock, approval, and retry checks."""
    return execute_replacement(
        order_ref,
        customer_ref,
        ticket_id=ticket_id,
        approved_by=approved_by,
        idempotency_key=idempotency_key,
    )


def run() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
