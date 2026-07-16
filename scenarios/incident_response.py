import random
from scenarios.base import Scenario, Tool


def build_scenario(fail_rate: float = 0.0, seed: int = 42) -> Scenario:
    rng = random.Random(seed)

    def check_service_metrics(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise TimeoutError("MetricsAPI: query timed out")
        return {"service": "checkout-api", "error_rate_pct": 23.4, "p99_latency_ms": 4800,
                "recent_deploy": "v2.14.0", "deployed_minutes_ago": 12}

    def rollback_deploy(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise RuntimeError("DeployAPI: rollback failed, orchestrator unreachable")
        return {"status": "ROLLED_BACK", "service": args.get("service"), "reverted_to": "v2.13.2"}

    def restart_service(args: dict) -> dict:
        if rng.random() < fail_rate:
            raise RuntimeError("OrchestratorAPI: restart command rejected")
        return {"status": "RESTARTED", "service": args.get("service")}

    return Scenario(
        id="incident_response",
        business_domain="Cloud Infrastructure",
        alert_text=("PagerDuty alert: checkout-api error rate at 23.4%, p99 latency 4800ms, "
                     "triggered 12 minutes after deploy v2.14.0 went live."),
        goal=("Diagnose the likely cause and autonomously take corrective action "
              "(rollback or restart) to restore service health, without waking a human on-call, "
              "unless the situation can't be resolved with available tools."),
        tools=[
            Tool("check_service_metrics", "Get current error rate, latency, and recent deploy info for a service.", check_service_metrics),
            Tool("rollback_deploy", "Roll back a service to its previous deployed version.", rollback_deploy),
            Tool("restart_service", "Restart a service's running instances.", restart_service),
        ],
        fail_rate=fail_rate,
    )
