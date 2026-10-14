"""Order + shipment API tools.

There is no real order system for this assignment, so `MockCommerceAPI` simulates one
from JSON files (with realistic latency and optional random 503s to exercise the
executor's retry policy). Swapping in a real API means re-implementing this class only -
the tools and workflows stay the same.
"""

from __future__ import annotations

import json
import logging
import random
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from workflow_agent.core.config import resolve_path
from workflow_agent.core.exceptions import ToolError, ToolInputError, TransientToolError
from workflow_agent.core.models import StepStatus, ToolResult
from workflow_agent.tools.registry import ToolContext, tool

logger = logging.getLogger(__name__)


class MockCommerceAPI:
    def __init__(self, orders_file: Path, shipments_file: Path, failure_rate: float = 0.0) -> None:
        self.orders_file = orders_file
        self.shipments_file = shipments_file
        self.failure_rate = failure_rate

    def _call(self, endpoint: str) -> None:
        time.sleep(random.uniform(0.02, 0.08))  # network latency
        if self.failure_rate and random.random() < self.failure_rate:
            logger.warning("Mock API %s returned 503", endpoint)
            raise TransientToolError(f"{endpoint} temporarily unavailable (HTTP 503)")

    @staticmethod
    @lru_cache(maxsize=8)
    def _load(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise ToolError(f"Data source not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def find_orders(self, kind: str, value: str) -> list[dict[str, Any]]:
        self._call("GET /orders")
        orders = self._load(self.orders_file)
        if kind == "order_id":
            return [o for o in orders if o["order_id"].upper() == value.upper()]
        if kind == "email":
            return [o for o in orders if o["customer_email"].lower() == value.lower()]
        raise ToolInputError(f"Unsupported identifier type '{kind}'")

    def get_shipment(self, shipment_id: str) -> dict[str, Any] | None:
        self._call("GET /shipments")
        return next((s for s in self._load(self.shipments_file) if s["shipment_id"] == shipment_id), None)


def _api(ctx: ToolContext, orders_file: str, shipments_file: str) -> MockCommerceAPI:
    return MockCommerceAPI(resolve_path(orders_file), resolve_path(shipments_file), ctx.settings.mock_api_failure_rate)


@tool(category="api")
def search_orders(
    identifier: dict[str, str] | None,
    ctx: ToolContext,
    orders_file: str = "data/samples/orders.json",
    shipments_file: str = "data/samples/shipments.json",
) -> ToolResult:
    """Order API: find orders by order ID or customer email."""
    if not identifier:
        raise ToolInputError("No validated identifier to search with")
    orders = _api(ctx, orders_file, shipments_file).find_orders(identifier["type"], identifier["value"])
    if not orders:
        return ToolResult(
            status=StepStatus.NEEDS_INPUT,
            needs=["identifier"],
            question=(
                f"I couldn't find any order for **{identifier['value']}**. "
                "Could you share another order ID (e.g. ORD-1001) or the email address used for the order?"
            ),
            message=f"No order found for {identifier['value']}",
        )
    return ToolResult(output=orders, message=f"Found {len(orders)} order(s)", metrics={"orders_found": len(orders)})


@tool(category="api")
def get_order_status(orders: list[dict[str, Any]]) -> ToolResult:
    """Order API: current status + items for each order."""
    rows = []
    for order in orders:
        items = "; ".join(f"{i['quantity']}x {i['name']} ({i['sku']})" for i in order.get("items", []))
        total = sum(i["quantity"] * i["unit_price"] for i in order.get("items", []))
        rows.append({
            "order_id": order["order_id"],
            "customer": order.get("customer_name"),
            "order_date": order.get("order_date"),
            "order_status": order.get("status"),
            "items": items,
            "order_total": round(total, 2),
        })
    return ToolResult(output=pd.DataFrame(rows), message=", ".join(f"{r['order_id']}: {r['order_status']}" for r in rows))


@tool(category="api")
def track_shipments(
    orders: list[dict[str, Any]],
    ctx: ToolContext,
    orders_file: str = "data/samples/orders.json",
    shipments_file: str = "data/samples/shipments.json",
) -> ToolResult:
    """Shipment API: carrier, tracking number, status and latest event for each order."""
    api = _api(ctx, orders_file, shipments_file)
    rows, warnings = [], []
    for order in orders:
        shipment_id = order.get("shipment_id")
        shipment = api.get_shipment(shipment_id) if shipment_id else None
        if shipment_id and shipment is None:
            warnings.append(f"Shipment {shipment_id} for {order['order_id']} not found at carrier")
        if shipment is None:
            rows.append({"order_id": order["order_id"], "shipment_status": "Not shipped yet",
                         "carrier": None, "tracking_number": None, "estimated_delivery": None,
                         "latest_update": None})
            continue
        events = shipment.get("events", [])
        latest = events[-1] if events else {}
        rows.append({
            "order_id": order["order_id"],
            "shipment_status": shipment.get("status"),
            "carrier": shipment.get("carrier"),
            "tracking_number": shipment.get("tracking_number"),
            "estimated_delivery": shipment.get("estimated_delivery"),
            "latest_update": f"{latest.get('timestamp', '')} - {latest.get('description', '')} ({latest.get('location', '')})" if latest else None,
        })
    return ToolResult(output=pd.DataFrame(rows), warnings=warnings,
                      message=", ".join(f"{r['order_id']}: {r['shipment_status']}" for r in rows))


@tool(category="api")
def summarize_order_status(order_status: Any, shipments: Any) -> ToolResult:
    """Merge order and shipment data into one status line per order."""
    orders = pd.DataFrame(order_status) if not isinstance(order_status, pd.DataFrame) else order_status
    ships = pd.DataFrame(shipments) if not isinstance(shipments, pd.DataFrame) else shipments
    merged = orders.merge(ships, on="order_id", how="left")
    return ToolResult(output=merged, message=f"Summarised {len(merged)} order(s)")
