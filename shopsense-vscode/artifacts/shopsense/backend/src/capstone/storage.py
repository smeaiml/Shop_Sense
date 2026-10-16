"""SQLite persistence for the mock commerce tables and support workflow state."""

from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

from capstone.settings import DATABASE_PATH, DATA_DIR, RUNTIME_DIR

_init_lock = RLock()
_initialized = False

TABLES: dict[str, tuple[str, ...]] = {
    "customers": ("customer_ref", "display_name", "city", "tier", "joined_on", "lifetime_orders", "return_rate", "flagged_for_abuse"),
    "products": ("sku", "title", "category", "price_inr", "seller_id", "in_stock", "warranty_months"),
    "orders": ("order_ref", "customer_ref", "sku", "quantity", "order_value_inr", "placed_at", "payment_method", "status", "delivery_promise_days", "actual_delivery_days"),
    "order_fulfilment": ("order_ref", "service_tier", "delivery_zone", "promised_by", "delivered_on", "days_late", "delay_credit_due_inr", "return_by", "warranty_until"),
    "shipments": ("tracking_id", "order_ref", "carrier", "last_scan", "last_scan_at", "scan_location"),
    "refunds": ("refund_id", "order_ref", "amount_inr", "reason_code", "status", "approved_by", "requested_on"),
}


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    db_path = Path(path or DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=20, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 20000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def database(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    db = connect(path)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _payload(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    raw = result.pop("payload_json", None)
    payload = json.loads(raw) if raw else {}
    payload.update({key: value for key, value in result.items() if value is not None})
    return payload


def initialize_store(path: Path | str | None = None, *, force: bool = False) -> None:
    """Create app tables and import the frozen CSV fixtures without overwriting edits."""
    global _initialized
    if path is None and _initialized and not force:
        return
    with _init_lock:
        if path is None and _initialized and not force:
            return
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        with database(path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_ref TEXT PRIMARY KEY, display_name TEXT, city TEXT, tier TEXT,
                    joined_on TEXT, lifetime_orders INTEGER, return_rate REAL,
                    flagged_for_abuse INTEGER, payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    sku TEXT PRIMARY KEY, title TEXT, category TEXT, price_inr REAL,
                    seller_id TEXT, in_stock INTEGER, warranty_months INTEGER,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    order_ref TEXT PRIMARY KEY, customer_ref TEXT NOT NULL, sku TEXT NOT NULL,
                    quantity INTEGER, order_value_inr REAL, placed_at TEXT, payment_method TEXT,
                    status TEXT, delivery_promise_days INTEGER, actual_delivery_days INTEGER,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_ref, order_ref);
                CREATE TABLE IF NOT EXISTS order_fulfilment (
                    order_ref TEXT PRIMARY KEY, service_tier TEXT, delivery_zone TEXT,
                    promised_by TEXT, delivered_on TEXT, days_late INTEGER,
                    delay_credit_due_inr REAL, return_by TEXT, warranty_until TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shipments (
                    tracking_id TEXT PRIMARY KEY, order_ref TEXT NOT NULL, carrier TEXT,
                    last_scan TEXT, last_scan_at TEXT, scan_location TEXT, payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_ref);
                CREATE TABLE IF NOT EXISTS refunds (
                    refund_id TEXT PRIMARY KEY, order_ref TEXT NOT NULL, amount_inr REAL NOT NULL,
                    reason_code TEXT, status TEXT NOT NULL, approved_by TEXT, requested_on TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_refunds_order ON refunds(order_ref);
                CREATE TABLE IF NOT EXISTS replacements (
                    replacement_id TEXT PRIMARY KEY, order_ref TEXT NOT NULL,
                    status TEXT NOT NULL, approved_by TEXT, created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS support_tickets (
                    ticket_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, customer_ref TEXT,
                    order_ref TEXT, raw_message TEXT NOT NULL, issue_type TEXT NOT NULL,
                    sentiment TEXT NOT NULL, urgency TEXT NOT NULL, status TEXT NOT NULL,
                    response TEXT, approval_required INTEGER NOT NULL DEFAULT 0,
                    approval_tier TEXT, created_at TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tickets_customer ON support_tickets(customer_ref, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status, created_at DESC);
                CREATE TABLE IF NOT EXISTS customer_memory (
                    customer_ref TEXT PRIMARY KEY, preferences_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_executions (
                    idempotency_key TEXT PRIMARY KEY, ticket_id TEXT NOT NULL,
                    action_type TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL,
                    event TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )
            for table, columns in TABLES.items():
                source = DATA_DIR / "mock_api" / f"{table}.csv"
                if not source.exists():
                    raise FileNotFoundError(f"Required ShopSense seed table is missing: {source}")
                with source.open("r", encoding="utf-8-sig", newline="") as stream:
                    for source_row in csv.DictReader(stream):
                        values = {key: source_row.get(key) for key in columns}
                        row_key = values[columns[0]]
                        if not row_key:
                            continue
                        _insert_seed_row(db, table, columns, values, source_row)
            if path is None:
                _initialized = True


def _typed_value(table: str, column: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if column in {"lifetime_orders", "warranty_months", "quantity", "delivery_promise_days", "actual_delivery_days", "days_late"}:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    if column in {"return_rate", "price_inr", "order_value_inr", "amount_inr", "delay_credit_due_inr"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if column in {"flagged_for_abuse", "in_stock"}:
        return int(str(value).strip().lower() in {"1", "true", "yes"})
    return str(value)


def _insert_seed_row(
    db: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
    values: dict[str, Any],
    source_row: dict[str, Any],
) -> None:
    key_col = columns[0]
    prepared = {column: _typed_value(table, column, values.get(column)) for column in columns}
    payload = json.dumps(source_row, ensure_ascii=False)
    names = ", ".join(columns) + ", payload_json"
    placeholders = ", ".join("?" for _ in range(len(columns) + 1))
    db.execute(
        f"INSERT OR IGNORE INTO {table} ({names}) VALUES ({placeholders})",
        [prepared[column] for column in columns] + [payload],
    )


def get_customer(customer_ref: str, *, path: Path | str | None = None) -> dict[str, Any] | None:
    initialize_store(path)
    with database(path) as db:
        row = db.execute(
            "SELECT * FROM customers WHERE customer_ref = ? COLLATE NOCASE",
            (customer_ref.strip(),),
        ).fetchone()
    return _payload(row) if row else None


def get_order_records(
    order_ref: str,
    customer_ref: str,
    *,
    path: Path | str | None = None,
) -> dict[str, Any] | None:
    """Return an order and related data only after exact customer ownership matches."""
    initialize_store(path)
    order_ref = order_ref.strip().upper()
    customer_ref = customer_ref.strip().upper()
    if not order_ref or not customer_ref:
        return None
    with database(path) as db:
        order_row = db.execute(
            "SELECT * FROM orders WHERE order_ref = ? COLLATE NOCASE AND customer_ref = ? COLLATE NOCASE",
            (order_ref, customer_ref),
        ).fetchone()
        if not order_row:
            return None
        order = _payload(order_row)
        product_row = db.execute(
            "SELECT * FROM products WHERE sku = ? COLLATE NOCASE",
            (str(order.get("sku", "")),),
        ).fetchone()
        shipment_row = db.execute(
            "SELECT * FROM shipments WHERE order_ref = ? COLLATE NOCASE ORDER BY last_scan_at DESC LIMIT 1",
            (order_ref,),
        ).fetchone()
        refund_rows = db.execute(
            "SELECT * FROM refunds WHERE order_ref = ? COLLATE NOCASE ORDER BY requested_on DESC",
            (order_ref,),
        ).fetchall()
        fulfilment_row = db.execute(
            "SELECT * FROM order_fulfilment WHERE order_ref = ? COLLATE NOCASE LIMIT 1",
            (order_ref,),
        ).fetchone()
        product = _payload(product_row) if product_row else None
    return {
        "order": order,
        "product": product,
        "category": product.get("category") if product else None,
        "shipment": _payload(shipment_row) if shipment_row else None,
        "refunds": [_payload(row) for row in refund_rows],
        "fulfilment": _payload(fulfilment_row) if fulfilment_row else None,
    }


def save_ticket(ticket: dict[str, Any], *, path: Path | str | None = None) -> None:
    initialize_store(path)
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(ticket, ensure_ascii=False, default=str)
    with database(path) as db:
        db.execute(
            """
            INSERT INTO support_tickets
            (ticket_id, thread_id, customer_ref, order_ref, raw_message, issue_type,
             sentiment, urgency, status, response, approval_required, approval_tier,
             created_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
              customer_ref=excluded.customer_ref, order_ref=excluded.order_ref,
              issue_type=excluded.issue_type, sentiment=excluded.sentiment,
              urgency=excluded.urgency, status=excluded.status, response=excluded.response,
              approval_required=excluded.approval_required, approval_tier=excluded.approval_tier,
              payload_json=excluded.payload_json
            """,
            (
                ticket.get("ticket_id"), ticket.get("thread_id", ticket.get("ticket_id")),
                ticket.get("customer_id"), ticket.get("order_id"), ticket.get("raw_message", ""),
                ticket.get("issue_type", "other"), ticket.get("sentiment", "neutral"),
                ticket.get("urgency", "low"), ticket.get("status", "open"),
                ticket.get("response"), int(bool(ticket.get("approval_required"))),
                ticket.get("approval_tier"), ticket.get("created_at", now), payload,
            ),
        )
        events = ticket.get("audit_events", [])
        for item in events:
            details = json.dumps(item.get("details", {}), ensure_ascii=False)
            event_name = item.get("event", "event")
            db.execute(
                """
                INSERT INTO audit_events(ticket_id, event, details_json, created_at)
                SELECT ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM audit_events
                    WHERE ticket_id = ? AND event = ? AND details_json = ?
                )
                """,
                (ticket.get("ticket_id"), event_name, details, now, ticket.get("ticket_id"), event_name, details),
            )
        customer_ref = ticket.get("customer_id")
        if customer_ref:
            db.execute(
                "INSERT OR IGNORE INTO customer_memory(customer_ref, preferences_json, updated_at) VALUES (?, '[]', ?)",
                (customer_ref, now),
            )


def list_tickets(*, status: str | None = None, limit: int = 50, path: Path | str | None = None) -> list[dict[str, Any]]:
    initialize_store(path)
    limit = max(1, min(int(limit), 200))
    with database(path) as db:
        if status:
            rows = db.execute(
                "SELECT * FROM support_tickets WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM support_tickets ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_payload(row) for row in rows]


def get_ticket(ticket_id: str, *, path: Path | str | None = None) -> dict[str, Any] | None:
    initialize_store(path)
    with database(path) as db:
        row = db.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?",
            (ticket_id.strip(),),
        ).fetchone()
    return _payload(row) if row else None


def get_customer_memory(customer_ref: str, *, path: Path | str | None = None) -> list[str]:
    initialize_store(path)
    with database(path) as db:
        row = db.execute(
            "SELECT preferences_json FROM customer_memory WHERE customer_ref = ? COLLATE NOCASE",
            (customer_ref.strip(),),
        ).fetchone()
    return json.loads(row["preferences_json"]) if row else []


def update_customer_memory(customer_ref: str, preferences: list[str], *, path: Path | str | None = None) -> None:
    initialize_store(path)
    clean = []
    for preference in preferences:
        value = str(preference).strip()
        if value and len(value) <= 240 and value not in clean:
            clean.append(value)
    if len(clean) > 20:
        raise ValueError("At most 20 customer preferences can be stored.")
    now = datetime.now(timezone.utc).isoformat()
    with database(path) as db:
        db.execute(
            """
            INSERT INTO customer_memory(customer_ref, preferences_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(customer_ref) DO UPDATE SET
              preferences_json=excluded.preferences_json, updated_at=excluded.updated_at
            """,
            (customer_ref.strip().upper(), json.dumps(clean, ensure_ascii=False), now),
        )


def dashboard_stats(*, path: Path | str | None = None) -> dict[str, Any]:
    initialize_store(path)
    with database(path) as db:
        open_tickets = db.execute(
            "SELECT COUNT(*) FROM support_tickets WHERE status IN ('needs_information','pending_human_review','pending_approval','needs_human_review')"
        ).fetchone()[0]
        pending_reviews = db.execute(
            "SELECT COUNT(*) FROM support_tickets WHERE status IN ('pending_human_review','pending_approval','needs_human_review')"
        ).fetchone()[0]
        today = datetime.now(timezone.utc).date().isoformat()
        resolved_today = db.execute(
            "SELECT COUNT(*) FROM support_tickets WHERE status IN ('resolved','review_completed','completed','answered') AND substr(created_at,1,10)=?",
            (today,),
        ).fetchone()[0]
        customers = db.execute(
            "SELECT COUNT(DISTINCT customer_ref) FROM support_tickets WHERE customer_ref IS NOT NULL"
        ).fetchone()[0]
    return {
        "open_tickets": open_tickets,
        "pending_reviews": pending_reviews,
        "resolved_today": resolved_today,
        "customers_served": customers,
        "recent_tickets": list_tickets(limit=8, path=path),
    }
