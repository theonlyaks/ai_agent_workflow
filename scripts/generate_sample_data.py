"""Generate the deterministic sample datasets in data/samples/ (simulated business systems).

    python scripts/generate_sample_data.py

The data is designed so every decision rule in the Excel file is exercised, including
edge cases (stock exactly at threshold, price diff exactly 10%, missing values, unknown
SKUs, duplicate keywords, an employee on leave, ...).
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"

PRODUCTS = [
    # sku, name, category, brand, color, material, price, unit_cost, collection, tags
    ("SKU-1001", "Classic Cotton T-Shirt", "Apparel", "Northwind", "White", "Cotton", 19.99, 6.50, "Core", "basics; tee"),
    ("SKU-1002", "Classic Cotton T-Shirt", "Apparel", "Northwind", "Black", "Cotton", 19.99, 6.50, "Core", "basics; tee"),
    ("SKU-1003", "Slim Fit Denim Jeans", "Apparel", "Northwind", "Indigo", "Denim", 59.00, 22.00, "Core", "denim"),
    ("SKU-1004", "Wool Blend Sweater", "Apparel", "Northwind", "Oatmeal", "Wool blend", 79.00, 30.00, "Core", "knitwear"),
    ("SKU-1005", "Leather Belt", "Accessories", "Northwind", "Brown", "Leather", 35.00, 9.00, "Core", "leather goods"),
    ("SKU-1006", "Canvas Tote Bag", "Accessories", "Northwind", "Natural", "Canvas", 24.00, 7.00, "Core", "bags"),
    ("SKU-1007", "Running Sneakers", "Footwear", "Stride", "Black", "Mesh", 89.00, 41.00, "Core", "running; shoes"),
    ("SKU-1008", "Hiking Boots", "Footwear", "Stride", "Brown", "Leather", 129.00, 58.00, "Core", "outdoor; boots"),
    ("SKU-1009", "Silk Scarf", "Accessories", "Northwind", "Navy", "Silk", 45.00, 12.00, "Summer 2026", "scarves"),
    ("SKU-1010", "Waterproof Rain Jacket", "Outerwear", "Northwind", "Olive", "Nylon", 110.00, 70.00, "Core", "rainwear"),
    ("SKU-1011", "Puffer Vest", "Outerwear", "Northwind", "Black", "Recycled polyester", 85.00, 33.00, "Core", "layering"),
    ("SKU-1012", "Linen Shirt", "Apparel", "Northwind", "White", "Linen", 49.00, 18.00, "Summer 2026", "summer"),
    ("SKU-1013", "Baseball Cap", "Accessories", "Northwind", "Navy", "Cotton twill", 22.00, 5.00, "Core", "headwear"),
    ("SKU-1014", "Ankle Socks (3-Pack)", "Apparel", "Northwind", "Grey", "Cotton blend", 12.00, 3.50, "Core", "basics"),
    ("SKU-1015", "Yoga Leggings", "Activewear", "Flexa", "Black", "Nylon spandex", 55.00, 20.00, "Core", "yoga"),
    ("SKU-1016", "Sports Bra", "Activewear", "Flexa", "Teal", "Nylon spandex", 39.00, 14.00, "Core", "training"),
    ("SKU-2001", "Merino Wool Turtleneck", "Knitwear", "Northwind", "Charcoal", "Merino wool", 95.00, 38.00, "Autumn 2026", "new collection; new arrival; autumn 2026"),
    ("SKU-2002", "Corduroy Overshirt", "Apparel", "Northwind", "Rust", "Cotton corduroy", 75.00, 29.00, "Autumn 2026", "new collection; new arrival; autumn 2026"),
    ("SKU-2003", "Quilted Shacket", "Outerwear", "Northwind", "Forest green", "Recycled polyester", 120.00, 52.00, "Autumn 2026", "new collection; new arrival; autumn 2026"),
    ("SKU-2004", "Chelsea Boots", "Footwear", "Stride", "Dark brown", "Suede", 140.00, 61.00, "Autumn 2026", "new collection; new arrival; autumn 2026"),
    ("SKU-2005", "Cashmere Beanie", "Accessories", "Northwind", "Camel", "Cashmere", 49.00, 21.00, "Autumn 2026", "new collection; new arrival; autumn 2026"),
    ("SKU-2006", "Plaid Wool Scarf", "Accessories", "Northwind", "Red plaid", "Wool", 59.00, 26.00, "Autumn 2026", "new collection; new arrival; autumn 2026"),
]


def products() -> None:
    frame = pd.DataFrame(PRODUCTS, columns=["sku", "product_name", "category", "brand", "color", "material",
                                            "price", "unit_cost", "collection", "tags"])
    frame["target_audience"] = ""
    frame.loc[frame["category"] == "Activewear", "target_audience"] = "Women who train"
    frame.to_csv(OUT / "products.csv", index=False)


def inventory() -> None:
    stock = {  # sku: (current_stock, minimum_stock, supplier, lead_time_days)
        "SKU-1001": (120, 50, "CottonCo", 7), "SKU-1002": (18, 40, "CottonCo", 7),
        "SKU-1003": (35, 30, "DenimWorks", 14), "SKU-1004": (8, 25, "KnitHouse", 21),
        "SKU-1005": (60, 20, "LeatherLine", 10), "SKU-1006": (12, 15, "BagMakers", 7),
        "SKU-1007": (0, 20, "Stride Supply", 14), "SKU-1008": (22, 22, "Stride Supply", 14),  # exactly at threshold
        "SKU-1009": (45, 10, "SilkRoad", 30), "SKU-1010": (5, 15, "RainGear", 12),
        "SKU-1011": (30, 12, "RainGear", 12), "SKU-1012": (14, 20, "LinenLab", 10),
        "SKU-1013": (75, 25, "CapCo", 5), "SKU-1014": (200, 100, "CottonCo", 7),
        "SKU-1015": (9, 30, "Flexa Mfg", 9), "SKU-1016": (None, 20, "Flexa Mfg", 9),  # missing stock count
    }
    names = {p[0]: (p[1], p[2], p[7]) for p in PRODUCTS}
    rows = []
    for sku, (current, minimum, supplier, lead) in stock.items():
        name, category, cost = names[sku]
        rows.append({"sku": sku, "product_name": name, "category": category, "current_stock": current,
                     "minimum_stock": minimum, "unit_cost": cost, "supplier": supplier, "lead_time_days": lead})
    pd.DataFrame(rows).to_csv(OUT / "inventory.csv", index=False)


def vendor_prices() -> None:
    change = {  # % change applied to the internal price
        "SKU-1001": 2.0, "SKU-1002": -3.0, "SKU-1003": 15.0, "SKU-1004": 4.5, "SKU-1005": 10.0,  # exactly 10% -> not flagged
        "SKU-1006": -1.5, "SKU-1007": -12.5, "SKU-1008": 6.0, "SKU-1009": 0.0, "SKU-1010": 25.0,
        "SKU-1011": -8.0, "SKU-1012": 3.0, "SKU-1013": -10.5, "SKU-1014": 1.0, "SKU-1015": 9.9,
        "SKU-2001": 5.0, "SKU-2002": -2.0, "SKU-2003": 11.0, "SKU-2004": 0.5, "SKU-2005": -4.0, "SKU-2006": 7.0,
        # SKU-1016 intentionally missing from the vendor list
    }
    price = {p[0]: p[6] for p in PRODUCTS}
    rows = [{"sku": sku, "vendor_name": "Global Apparel Supply", "vendor_price": round(price[sku] * (1 + pct / 100), 2)}
            for sku, pct in change.items()]
    rows.append({"sku": "SKU-3001", "vendor_name": "Global Apparel Supply", "vendor_price": 29.0})  # unknown internally
    pd.DataFrame(rows).to_csv(OUT / "vendor_prices.csv", index=False)


def vendor_upload() -> None:
    """A deliberately messy vendor spreadsheet for WF003."""
    rows = [
        [" VND-501 ", "Organic Cotton Hoodie", "EcoWear", "Sage", "18.50", "120", "Apparel"],
        ["VND-502", "Bamboo Socks 5-Pack", "EcoWear", "Mixed", "6.20", "300", "Apparel"],
        [None, "Recycled Denim Jacket", "EcoWear", "Blue", "32.00", "45", "Outerwear"],  # missing SKU
        ["VND-504", "  ", "EcoWear", "Black", "11.00", "80", "Accessories"],  # blank name
        ["VND-505", "Hemp Backpack", "TrailGood", "Khaki", "N/A", "60", "Accessories"],  # bad cost (warning only)
        ["VND-506", "Merino Running Tee", "TrailGood", "Grey", "21.75", "150", "Activewear"],
        [None, None, "TrailGood", "Red", "9.99", "20", "Accessories"],  # missing both
        ["VND-508", "Trail Running Shoes", "TrailGood", "Orange", "48.00", "75", "Footwear"],
        ["VND-509", "Packable Rain Poncho", "TrailGood", "Yellow", "12.40", "dozens", "Outerwear"],  # bad qty
        ["VND-510", "Wool Hiking Socks", "TrailGood", "Charcoal", "7.80", "220", "Apparel"],
        ["VND-511", "Insulated Water Bottle", "TrailGood", "Steel", "14.00", "140", "Accessories"],
        ["VND-512", "Fleece Neck Gaiter", "EcoWear", "Navy", "5.50", "260", "Accessories"],
    ]
    columns = [" Item Code ", "Product Title", "Brand Name", "Colour", "Unit Cost ($)", "Qty Available", "Category"]
    pd.DataFrame(rows, columns=columns).to_excel(OUT / "vendor_upload.xlsx", index=False)


def orders_and_shipments() -> None:
    orders = [
        {"order_id": "ORD-1001", "customer_name": "Jane Doe", "customer_email": "jane.doe@example.com",
         "order_date": "2026-10-09", "status": "Shipped", "shipment_id": "SHP-5001",
         "items": [{"sku": "SKU-1004", "name": "Wool Blend Sweater", "quantity": 1, "unit_price": 79.0},
                   {"sku": "SKU-1013", "name": "Baseball Cap", "quantity": 2, "unit_price": 22.0}]},
        {"order_id": "ORD-1002", "customer_name": "Jane Doe", "customer_email": "jane.doe@example.com",
         "order_date": "2026-10-13", "status": "Processing", "shipment_id": None,
         "items": [{"sku": "SKU-2001", "name": "Merino Wool Turtleneck", "quantity": 1, "unit_price": 95.0}]},
        {"order_id": "ORD-1003", "customer_name": "Alex Kim", "customer_email": "alex.kim@example.com",
         "order_date": "2026-10-02", "status": "Delivered", "shipment_id": "SHP-5002",
         "items": [{"sku": "SKU-1007", "name": "Running Sneakers", "quantity": 1, "unit_price": 89.0}]},
        {"order_id": "ORD-1004", "customer_name": "Priya Shah", "customer_email": "priya.shah@example.com",
         "order_date": "2026-10-08", "status": "Cancelled", "shipment_id": None,
         "items": [{"sku": "SKU-1010", "name": "Waterproof Rain Jacket", "quantity": 1, "unit_price": 110.0}]},
        {"order_id": "ORD-1005", "customer_name": "Sam Lee", "customer_email": "sam.lee@example.com",
         "order_date": "2026-10-06", "status": "Shipped", "shipment_id": "SHP-5003",
         "items": [{"sku": "SKU-1008", "name": "Hiking Boots", "quantity": 1, "unit_price": 129.0},
                   {"sku": "SKU-1014", "name": "Ankle Socks (3-Pack)", "quantity": 3, "unit_price": 12.0}]},
    ]
    shipments = [
        {"shipment_id": "SHP-5001", "carrier": "UPS", "tracking_number": "1Z999AA10123456784", "status": "In transit",
         "estimated_delivery": "2026-10-16",
         "events": [{"timestamp": "2026-10-10 09:12", "location": "Newark, NJ", "description": "Picked up"},
                    {"timestamp": "2026-10-12 18:40", "location": "Columbus, OH", "description": "Departed facility"},
                    {"timestamp": "2026-10-14 07:05", "location": "Chicago, IL", "description": "Arrived at regional hub"}]},
        {"shipment_id": "SHP-5002", "carrier": "FedEx", "tracking_number": "7489 2210 5531", "status": "Delivered",
         "estimated_delivery": "2026-10-05",
         "events": [{"timestamp": "2026-10-03 11:00", "location": "Memphis, TN", "description": "In transit"},
                    {"timestamp": "2026-10-05 14:22", "location": "Austin, TX", "description": "Delivered - left at front door"}]},
        {"shipment_id": "SHP-5003", "carrier": "DHL", "tracking_number": "JD014600006281234567", "status": "Delayed",
         "estimated_delivery": "2026-10-17",
         "events": [{"timestamp": "2026-10-07 10:30", "location": "Leipzig, DE", "description": "Shipment picked up"},
                    {"timestamp": "2026-10-11 16:45", "location": "Cincinnati, OH", "description": "Customs clearance delay"}]},
    ]
    (OUT / "orders.json").write_text(json.dumps(orders, indent=2), encoding="utf-8")
    (OUT / "shipments.json").write_text(json.dumps(shipments, indent=2), encoding="utf-8")


def product_catalog() -> None:
    """Catalog export with planted duplicates for WF006."""
    rows = [
        ("SKU-1001", "Classic Cotton T-Shirt", "Northwind", "Apparel", "White", "M", "Cotton", 19.99),
        ("sku-1001 ", "Classic Cotton Tee", "Northwind", "Apparel", "White", "M", "Cotton", 19.99),  # same SKU, messy
        ("SKU-1003", "Slim Fit Denim Jeans", "Northwind", "Apparel", "Indigo", "32", "Denim", 59.00),
        ("SKU-1203", "Slim-Fit Denim Jeans", "Northwind", "Apparel", "Indigo", "32", "Denim", 59.00),  # near-identical
        ("SKU-1007", "Running Sneakers", "Stride", "Footwear", "Black", "42", "Mesh", 89.00),
        ("SKU-1077", "Running Sneaker", "Stride", "Footwear", "Black", "42", "Mesh / rubber", 89.00),  # 3 of 4 attributes
        ("SKU-1010", "Waterproof Rain Jacket", "Northwind", "Outerwear", "Olive", "L", "Nylon", 110.00),
        ("SKU-1910", "Rain Jacket - Waterproof", "Northwind", "Outerwear", "Olive", "L", "Nylon", 110.00),  # reordered words
        ("SKU-1012", "Linen Shirt", "Northwind", "Apparel", "White", "M", "Linen", 49.00),
        ("SKU-1112", "Linen Shirt", "Northwind", "Apparel", "Navy", "L", "Linen", 49.00),  # a variant, NOT a duplicate
        ("SKU-1004", "Wool Blend Sweater", "Northwind", "Apparel", "Oatmeal", "M", "Wool blend", 79.00),
        ("SKU-1005", "Leather Belt", "Northwind", "Accessories", "Brown", "One size", "Leather", 35.00),
        ("SKU-1006", "Canvas Tote Bag", "Northwind", "Accessories", "Natural", "One size", "Canvas", 24.00),
        ("SKU-1008", "Hiking Boots", "Stride", "Footwear", "Brown", "43", "Leather", 129.00),
        ("SKU-1015", "Yoga Leggings", "Flexa", "Activewear", "Black", "S", "Nylon spandex", 55.00),
        ("SKU-2001", "Merino Wool Turtleneck", "Northwind", "Knitwear", "Charcoal", "M", "Merino wool", 95.00),
        ("SKU-2004", "Chelsea Boots", "Stride", "Footwear", "Dark brown", "42", "Suede", 140.00),
        ("SKU-2104", "Chelsea Boot", "Stride", "Footwear", "Dark brown", "42", "Suede", 140.00),  # singular/plural
    ]
    pd.DataFrame(rows, columns=["sku", "product_name", "brand", "category", "color", "size", "material", "price"]).to_csv(
        OUT / "product_catalog.csv", index=False)


def keywords_and_categories() -> None:
    keywords = [
        ("buy running shoes", 2400), ("Buy Running Shoes ", 2400), ("best running shoes 2026", 1900),
        ("how to clean suede chelsea boots", 880), ("chelsea boots discount code", 590), ("merino wool turtleneck", 720),
        ("what is merino wool", 1300), ("waterproof rain jacket women", 1600), ("rain jacket vs poncho", 320),
        ("northwind apparel login", 210), ("northwind store near me", 480), ("cheap hiking boots sale", 1100),
        ("how to wash a wool sweater", 2900), ("linen shirt men", 1400), ("best yoga leggings with pockets", 1000),
        ("cashmere beanie", 390), ("canvas tote bag with zipper", 260), ("hiking boots size guide", 450),
        ("northwind return policy", 350), ("order wool scarf online", 170), ("waterproof rain jacket women", 1600),
        ("corduroy overshirt outfit ideas", 230), ("sports bra high support", 880), ("leather belt brown men", 540),
    ]
    pd.DataFrame(keywords, columns=["keyword", "search_volume"]).to_csv(OUT / "keywords.csv", index=False)
    categories = [
        ("Apparel", "/collections/apparel", "/journal/apparel-care-and-style"),
        ("Knitwear", "/collections/knitwear", "/journal/knitwear-guide"),
        ("Outerwear", "/collections/outerwear", "/journal/outerwear-guide"),
        ("Footwear", "/collections/footwear", "/journal/footwear-care-and-sizing"),
        ("Accessories", "/collections/accessories", "/journal/accessories-guide"),
        ("Activewear", "/collections/activewear", "/journal/activewear-guide"),
        ("Brand & Customer Service", "/pages/help-center", "/pages/help-center"),
    ]
    pd.DataFrame(categories, columns=["category", "target_page", "guide_page"]).to_csv(OUT / "categories.csv", index=False)


def employees_and_tasks() -> None:
    employees = [
        ("E01", "Aarav Mehta", "Senior Backend Developer", "python;fastapi;postgresql;aws;docker", 40, 28, "available"),
        ("E02", "Sofia Martins", "Backend Developer", "python;django;postgresql;redis", 40, 18, "available"),
        ("E03", "Liam Chen", "Frontend Developer", "react;typescript;css;next.js", 40, 20, "available"),
        ("E04", "Fatima Khan", "Full Stack Developer", "python;react;fastapi;docker", 40, 38, "available"),
        ("E05", "Noah Williams", "DevOps Engineer", "aws;docker;kubernetes;terraform", 40, 15, "available"),
        ("E06", "Emma Rossi", "Mobile Developer", "swift;kotlin;flutter", 40, 10, "on_leave"),
        ("E07", "Oliver Brown", "QA Engineer", "selenium;python;pytest", 40, 25, "available"),
        ("E08", "Mia Johnson", "Data Engineer", "python;spark;sql;airflow", 40, 39, "available"),
        ("E09", "Lucas Silva", "Frontend Developer", "react;javascript;css", 40, 36, "available"),
    ]
    pd.DataFrame(employees, columns=["employee_id", "name", "role", "skills", "capacity_hours", "current_workload_hours",
                                     "availability"]).to_csv(OUT / "employees.csv", index=False)
    tasks = [
        ("T-201", "Fix payment API timeouts under peak load", "python;fastapi;postgresql", "urgent", "2026-10-16", 6),
        ("T-202", "Build the new product filter UI", "react;typescript", "high", "2026-10-24", 16),
        ("T-203", "Move CI pipelines to GitHub Actions", "docker;aws", "medium", "2026-11-05", 12),
        ("T-204", "iOS app crashes on checkout", "swift", "urgent", "2026-10-15", 8),
        ("T-205", "Nightly sales data pipeline is failing", "python;airflow;sql", "high", "2026-10-18", 5),
    ]
    pd.DataFrame(tasks, columns=["task_id", "title", "required_skills", "priority", "deadline", "estimated_hours"]).to_csv(
        OUT / "tasks.csv", index=False)


def execution_logs() -> None:
    """~300 historical runs (step-level rows) with a realistic failure / latency profile for WF010."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from workflow_agent.registry.excel_loader import load_workflow_definitions

    definitions = load_workflow_definitions(ROOT / "data" / "AI_Agent_Workflow_Assessment.xlsx")
    rng = random.Random(42)
    profile = {  # workflow: (failure rate, {step index: (mean ms, jitter)}, [(failing step, error)])
        "WF001": (0.03, {}, [(1, "File not found: inventory.csv")]),
        "WF002": (0.05, {}, [(2, "Vendor price file has no 'sku' column")]),
        "WF003": (0.16, {}, [(1, "Unsupported file format '.pdf'"), (4, "Required column(s) ['sku'] could not be found")]),
        "WF004": (0.04, {2: (2600, 800), 3: (1500, 400), 4: (1200, 300), 5: (1300, 300)}, [(2, "LLM request timed out")]),
        "WF005": (0.21, {2: (420, 200), 4: (650, 300)}, [(4, "Shipment API timeout (gave up after 3 attempts)"),
                                                        (2, "GET /orders temporarily unavailable (HTTP 503)")]),
        "WF006": (0.02, {4: (900, 300)}, [(1, "File not found: product_catalog.csv")]),
        "WF007": (0.06, {2: (1800, 500), 4: (2400, 600), 5: (2300, 600), 6: (2600, 700)},
                  [(1, "Missing required information: campaign goal")]),
        "WF008": (0.09, {3: (7800, 2500), 4: (6400, 2000)}, [(3, "Rate limited by the Claude API (429) after retries")]),
        "WF009": (0.05, {1: (1900, 500), 6: (1700, 400)}, [(5, "No available employee has the required skills")]),
        "WF010": (0.01, {6: (2500, 600)}, [(1, "Execution log file is empty")]),
    }
    start = datetime(2026, 9, 14, 8, 0)
    runs_per_workflow = 30
    # Exactly round(rate * 30) failing runs per workflow, at random positions -> stable, readable rates
    failing = {
        wf: set(rng.sample(range(runs_per_workflow), round(rate * runs_per_workflow)))
        for wf, (rate, _, _) in profile.items()
    }
    rows = []
    for n in range(runs_per_workflow * len(definitions)):
        definition = definitions[n % len(definitions)]
        rate, slow, errors = profile[definition.workflow_id]
        timestamp = start + timedelta(minutes=rng.randint(0, 30 * 24 * 60))
        run_id = f"hist-{n + 1:04d}"
        is_failure = (n // len(definitions)) in failing[definition.workflow_id]
        fail_at, error = rng.choice(errors) if is_failure else (None, None)
        for index, step in enumerate(definition.steps, start=1):
            mean, jitter = slow.get(index, (rng.randint(40, 260), 60))
            failed = index == fail_at
            rows.append({
                "run_id": run_id, "timestamp": timestamp.isoformat(timespec="seconds"),
                "workflow_id": definition.workflow_id, "workflow_name": definition.name, "step": step,
                "status": "failed" if failed else "success",
                "duration_ms": max(5, int(rng.gauss(mean, jitter))), "error": error if failed else "",
            })
            timestamp += timedelta(milliseconds=rows[-1]["duration_ms"])
            if failed:
                break
    pd.DataFrame(rows).to_csv(OUT / "execution_logs.csv", index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    products()
    inventory()
    vendor_prices()
    vendor_upload()
    orders_and_shipments()
    product_catalog()
    keywords_and_categories()
    employees_and_tasks()
    execution_logs()
    print(f"Sample data written to {OUT}")
    for path in sorted(OUT.iterdir()):
        print(f"  {path.name:<22} {path.stat().st_size:>8,} bytes")


if __name__ == "__main__":
    main()
