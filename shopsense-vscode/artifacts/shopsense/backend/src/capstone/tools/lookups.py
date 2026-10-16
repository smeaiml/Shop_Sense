"""Entity-scoped lookups for ShopSense mock tables."""

from typing import Any

import pandas as pd

from capstone.tools.repository import _load_table, lookup_order


def lookup_product(sku: str) -> dict[str, Any]:
    """Look up a product by SKU."""
    if not sku or not sku.strip():
        return {"found": False, "message": "Please provide a product SKU."}
    products = _load_table("products")
    rows = products[products["sku"].astype(str).str.casefold() == sku.strip().casefold()]
    if rows.empty:
        return {"found": False, "message": "Product not found."}
    row = rows.iloc[0].to_dict()
    product = {
        key: (None if pd.isna(value) else value.item() if hasattr(value, "item") else value)
        for key, value in row.items()
    }
    return {"found": True, "product": product}


def lookup_customer(customer_ref: str) -> dict[str, Any]:
    """Return only basic customer details; do not expose internal abuse flags."""
    if not customer_ref or not customer_ref.strip():
        return {"found": False, "message": "Please provide a customer reference."}
    customers = _load_table("customers")
    rows = customers[
        customers["customer_ref"].astype(str).str.casefold() == customer_ref.strip().casefold()
    ]
    if rows.empty:
        return {"found": False, "message": "Customer not found."}
    row = rows.iloc[0]
    safe_fields = (
        "customer_ref", "display_name", "city", "tier",
        "joined_on", "lifetime_orders", "return_rate",
    )
    customer = {}
    for field in safe_fields:
        if field in row.index:
            value = row[field]
            customer[field] = None if str(value) == "nan" else (value.item() if hasattr(value, "item") else value)
    return {"found": True, "customer": customer}


def lookup_shipment(order_ref: str, customer_ref: str) -> dict[str, Any]:
    """Return shipment data only after verifying order ownership."""
    order_result = lookup_order(order_ref, customer_ref)
    if not order_result.get("found"):
        return {"found": False, "message": "Order not found for this customer."}
    return {
        "found": True,
        "order_ref": order_result["order"]["order_ref"],
        "shipment": order_result.get("shipment"),
        "fulfilment": order_result.get("fulfilment"),
    }
