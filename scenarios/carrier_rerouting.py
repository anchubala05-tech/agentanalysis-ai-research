import random
from scenarios.base import Scenario, Tool


def build_scenario(fail_rate: float = 0.0, seed: int = 42) -> Scenario:
    rng = random.Random(seed)

    def get_alternative_carriers(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise TimeoutError("CarrierNetworkAPI: request timed out")
        return {"carriers": [
            {"id": "CAR-1", "name": "Atlas Freight", "eta_hours": 11, "cost_usd": 4200, "reliability": 0.94},
            {"id": "CAR-2", "name": "Meridian Logistics", "eta_hours": 16, "cost_usd": 2800, "reliability": 0.81},
        ]}

    def book_carrier(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise ConnectionError("BookingAPI: failed to confirm booking")
        return {"status": "CONFIRMED", "carrier_id": args.get("carrier_id"), "confirmation": f"CONF-{rng.randint(1000,9999)}"}

    return Scenario(
        id="carrier_rerouting",
        business_domain="Logistics",
        alert_text=("Telemetry alert: Shipment SHP-88213 (Memphis, TN -> Columbus, OH). "
                     "Current carrier Northline Carriers reports mechanical failure 40mi outside Memphis. "
                     "SLA: 18 hours remaining."),
        goal=("Evaluate alternative carriers and autonomously book a reroute that meets the SLA, "
              "without asking a human, unless no viable option exists."),
        tools=[
            Tool("get_alternative_carriers", "Fetch available alternative carriers with ETA, cost, reliability.", get_alternative_carriers),
            Tool("book_carrier", "Book a reroute with a chosen carrier_id.", book_carrier),
        ],
        fail_rate=fail_rate,
    )
