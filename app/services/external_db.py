"""
Service for fetching orders and order_items from the external Postgres DB.
"""
import psycopg2
import psycopg2.extras
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config import settings

# Store ID mapping (matches stores table in external DB)
STORE_ID_MAP = {
    "bestshield": 7,
    "shabah": 8,
    "alarabi": 10,
    "hero": 6,
    "fawzan": 9,
}


def get_external_connection():
    return psycopg2.connect(
        host=settings.EXTERNAL_DB_HOST,
        port=int(settings.EXTERNAL_DB_PORT),
        user=settings.EXTERNAL_DB_USERNAME,
        password=settings.EXTERNAL_DB_PASSWORD,
        dbname=settings.EXTERNAL_DB_NAME,
    )


def get_store_id(brand_key: str) -> Optional[int]:
    return STORE_ID_MAP.get(brand_key)


def fetch_order_statuses(brand_key: str) -> List[str]:
    """Fetch distinct order statuses for a brand."""
    store_id = get_store_id(brand_key)
    if not store_id:
        return []

    conn = get_external_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT status_name FROM orders WHERE store_id = %s AND status_name IS NOT NULL ORDER BY (status_name ~ '^[a-zA-Z]'), status_name",
            (store_id,)
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_order_items(
    brand_key: str,
    status_values: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch order items (sku, quantity) joined with orders for filtering.
    Returns: {
        "items": [ {"sku": "...", "quantity": N}, ... ],
        "total_orders": int,
        "filtered_orders": int,
    }
    """
    store_id = get_store_id(brand_key)
    if not store_id:
        raise ValueError(f"لا يوجد متجر مرتبط بـ: {brand_key}")

    conn = get_external_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Count total orders
        cur.execute("SELECT COUNT(*) FROM orders WHERE store_id = %s", (store_id,))
        total_orders = cur.fetchone()[0]

        # Build filtered query
        where_clauses = ["o.store_id = %s", "oi.sku IS NOT NULL"]
        params: list = [store_id]

        if status_values:
            placeholders = ",".join(["%s"] * len(status_values))
            where_clauses.append(f"o.status_name IN ({placeholders})")
            params.extend(status_values)

        if date_from:
            where_clauses.append("o.date >= %s")
            params.append(date_from)

        if date_to:
            where_clauses.append("o.date <= %s")
            params.append(date_to + " 23:59:59")

        where_sql = " AND ".join(where_clauses)

        # Count filtered orders
        cur.execute(
            f"SELECT COUNT(DISTINCT o.id) FROM orders o JOIN order_items oi ON oi.order_id = o.id WHERE {where_sql}",
            params
        )
        filtered_orders = cur.fetchone()[0]

        # Fetch items
        cur.execute(
            f"""
            SELECT oi.sku, oi.quantity
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE {where_sql}
            """,
            params
        )

        items = [{"sku": row["sku"], "quantity": int(row["quantity"] or 1)} for row in cur.fetchall()]

        return {
            "items": items,
            "total_orders": total_orders,
            "filtered_orders": filtered_orders,
        }
    finally:
        conn.close()
