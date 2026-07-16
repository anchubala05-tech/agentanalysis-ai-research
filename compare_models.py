"""
Runs BOTH models through all 4 business scenarios and prints/saves what
each one actually did. This is the core artifact for the assignment --
side-by-side trajectories you can read and reason about, not just a score.

Usage examples:
    # Compare Claude vs a local Ollama model, no injected failures
    python compare_models.py --claude-model claude-sonnet-4-6 --ollama-model llama3.1

    # Same, but inject a 40% tool failure rate to see how each model recovers
    python compare_models.py --ollama-model qwen2.5:14b --fail-rate 0.4

    # Dry run with no real models, just to check the harness works
    python compare_models.py --mock
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # reads .env in the current directory, if present

from scenarios import carrier_rerouting, incident_response, support_ticket, inventory_replenishment
from providers.llm_providers import get_provider
from agent_loop import run_agent
from rubric import score_run, score_dict

SCENARIO_MODULES = [carrier_rerouting, incident_response, support_ticket, inventory_replenishment]
LOG_DIR = Path(__file__).parent / "logs"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--closed-source", default="gemini", choices=["claude", "gemini"],
                         help="Which closed-source provider to use. 'gemini' works on Google's free tier.")
    parser.add_argument("--claude-model", default="claude-sonnet-4-6")
    parser.add_argument("--gemini-model", default="gemini-3-flash")
    parser.add_argument("--ollama-model", default="llama3.1")
    parser.add_argument("--fail-rate", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mock", action="store_true", help="Use mock provider for both slots (harness test only)")
    args = parser.parse_args()

    if args.mock:
        providers = {"closed_source": get_provider("mock"), "open_source": get_provider("mock")}
    else:
        if args.closed_source == "gemini":
            closed = get_provider("gemini", model=args.gemini_model)
        else:
            closed = get_provider("claude", model=args.claude_model)
        providers = {
            "closed_source": closed,
            "open_source": get_provider("ollama", model=args.ollama_model),
        }

    all_results = []
    all_scores = []

    for slot, provider in providers.items():
        print(f"\n{'='*60}\n{slot.upper()}: {provider.name}\n{'='*60}")
        for mod in SCENARIO_MODULES:
            scenario = mod.build_scenario(fail_rate=args.fail_rate, seed=args.seed)
            print(f"\n--- {scenario.id} ---")
            result = run_agent(scenario, provider)
            result["slot"] = slot
            all_results.append(result)

            score = score_run(result)
            all_scores.append(score)

            for step in result["trajectory"]:
                print(f"  [{step['step']}] {step['event']}"
                      + (f" tool={step['tool']}" if "tool" in step else ""))
            print(f"  FINAL: {'ESCALATED' if result['escalated'] else 'RESOLVED'} "
                  f"in {result['steps_taken']} steps  |  score={score.total}")
            if result["final_decision"]:
                print(f"  DECISION: {result['final_decision']}")

    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / "comparison_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    with open(LOG_DIR / "scores.json", "w") as f:
        json.dump([score_dict(s) for s in all_scores], f, indent=2)

    print(f"\n\n{'='*60}\nSUMMARY\n{'='*60}")
    header = f"{'scenario':25s} {'slot':15s} {'outcome':10s} {'tool':5s} {'proto':6s} {'recov':6s} {'eff':4s} {'total':6s}"
    print(header)
    print("-" * len(header))
    for r, s in zip(all_results, all_scores):
        print(f"{s.scenario_id:25s} {r['slot']:15s} {s.outcome:10s} "
              f"{s.tool_usage:<5d} {s.protocol_adherence:<6d} {s.error_recovery:<6d} "
              f"{s.efficiency:<4d} {s.total:<6.2f}")

    print(f"\nPer-model averages:")
    for slot in providers:
        slot_scores = [s.total for r, s in zip(all_results, all_scores) if r["slot"] == slot]
        if slot_scores:
            print(f"  {slot}: avg={sum(slot_scores)/len(slot_scores):.2f}")

    print(f"\nFull results: {LOG_DIR/'comparison_results.json'}")
    print(f"Scores: {LOG_DIR/'scores.json'}")


if __name__ == "__main__":
    main()
