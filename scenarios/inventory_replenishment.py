import random
from scenarios.base import Scenario, Tool


def build_scenario(fail_rate: float = 0.0, seed: int = 42) -> Scenario:
    rng = random.Random(seed)

    def check_supplier_options(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise TimeoutError("SupplierAPI: request timed out")
        return {"suppliers": [
            {"id": "SUP-1", "name": "Global Parts Co", "unit_price_usd": 4.20, "lead_time_days": 5, "min_order_qty": 500},
            {"id": "SUP-2", "name": "FastStock Inc", "unit_price_usd": 5.10, "lead_time_days": 2, "min_order_qty": 200},
        ]}

    def place_purchase_order(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise RuntimeError("ProcurementAPI: PO submission failed")
        return {"status": "PO_PLACED", "supplier_id": args.get("supplier_id"),
                "quantity": args.get("quantity"), "po_number": f"PO-{rng.randint(10000,99999)}"}

    return Scenario(
        id="inventory_replenishment",
        business_domain="Supply Chain",
        alert_text=("Inventory alert: SKU-9931 (M8 bolts) has dropped to 80 units, below the "
                     "300-unit reorder threshold. Current daily usage: 60 units/day."),
        goal=("Evaluate supplier options and autonomously place a purchase order that avoids "
              "a stockout given the usage rate, without waiting for human sign-off, unless no "
              "supplier can meet the timeline."),
        tools=[
            Tool("check_supplier_options", "Get available suppliers with price, lead time, min order qty.", check_supplier_options),
            Tool("place_purchase_order", "Place a PO with supplier_id and quantity.", place_purchase_order),
        ],
        fail_rate=fail_rate,
    )
