import random
from scenarios.base import Scenario, Tool


def build_scenario(fail_rate: float = 0.0, seed: int = 42) -> Scenario:
    rng = random.Random(seed)

    def check_order_status(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise TimeoutError("OrdersAPI: lookup timed out")
        return {"order_id": "ORD-55210", "status": "delivered", "delivered_days_ago": 9,
                "item": "Wireless Headphones", "price_usd": 89.99, "return_window_days": 30}

    def issue_refund(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise RuntimeError("PaymentsAPI: refund could not be processed")
        return {"status": "REFUNDED", "order_id": args.get("order_id"), "amount_usd": args.get("amount_usd")}

    return Scenario(
        id="support_ticket",
        business_domain="Customer Support",
        alert_text=("Support ticket #4471: Customer says wireless headphones (Order ORD-55210) "
                     "stopped charging after 9 days and wants a refund. Customer tone: frustrated, "
                     "second message on this issue."),
        goal=("Verify the order is eligible and autonomously resolve the ticket (issue the refund) "
              "without escalating to a human agent, unless the order is not eligible."),
        tools=[
            Tool("check_order_status", "Look up an order's status, item, price, and return window.", check_order_status),
            Tool("issue_refund", "Issue a refund for an order_id and amount_usd.", issue_refund),
        ],
        fail_rate=fail_rate,
    )
