"""
Scores a single agent run (the dict returned by agent_loop.run_agent) on
four 0-2 dimensions. Works identically across all 4 use cases because it
only reads the generic trajectory shape (step/event/tool/...), never
anything domain-specific.
"""

from dataclasses import dataclass, asdict


@dataclass
class RunScore:
    scenario_id: str
    model: str
    outcome: str              # "resolved" | "escalated" | "unresolved"
    tool_usage: int            # 0-2: did it call a real tool before deciding, vs guessing blind
    error_recovery: int        # 0-2: how it handled tool_call_error events, if any occurred
    protocol_adherence: int    # 0-2: valid JSON / valid tool names, vs unparseable_response / invalid_tool_name
    efficiency: int            # 0-2: steps taken
    total: float
    notes: list[str]


def score_run(result: dict) -> RunScore:
    traj = result["trajectory"]
    notes = []

    # --- tool_usage ---
    tool_calls = [s for s in traj if s["event"] in ("tool_call_success", "tool_call_error")]
    decided_without_any_tool = (
        result["final_decision"] is not None
        and not any(s["event"] == "tool_call_success" for s in traj)
    )
    if decided_without_any_tool:
        tool_usage = 0
        notes.append("Reached a final decision without a single successful tool call -- likely guessed.")
    elif tool_calls:
        tool_usage = 2
    else:
        tool_usage = 1
        notes.append("No tool calls at all (may be fine only if scenario had zero viable tools).")

    # --- protocol_adherence ---
    bad_events = [s for s in traj if s["event"] in ("unparseable_response", "invalid_tool_name", "unknown_action")]
    if not bad_events:
        protocol_adherence = 2
    elif len(bad_events) == 1:
        protocol_adherence = 1
        notes.append(f"One protocol slip: {bad_events[0]['event']}.")
    else:
        protocol_adherence = 0
        notes.append(f"{len(bad_events)} protocol slips (bad JSON / invalid tool names) -- weak instruction-following.")

    # --- error_recovery ---
    errors = [s for s in traj if s["event"] == "tool_call_error"]
    successes_after_error = any(
        s["event"] == "tool_call_success"
        for i, s in enumerate(traj)
        if any(e["step"] < s["step"] for e in errors)
    )
    if not errors:
        error_recovery = 2
        notes.append("No injected tool failures this run.")
    elif successes_after_error and not result["escalated"]:
        error_recovery = 2
        notes.append(f"Recovered from {len(errors)} tool failure(s) and still resolved the task.")
    elif result["escalated"]:
        error_recovery = 1
        notes.append("Escalated after failures -- acceptable but not optimal recovery.")
    else:
        error_recovery = 0
        notes.append("Hit tool failures and did not recover or escalate cleanly.")

    # --- efficiency ---
    steps = result["steps_taken"]
    if steps <= 3:
        efficiency = 2
    elif steps <= 5:
        efficiency = 1
    else:
        efficiency = 0
        notes.append(f"Took {steps} steps -- inefficient.")

    if result["escalated"]:
        outcome = "escalated"
    elif result["final_decision"]:
        outcome = "resolved"
    else:
        outcome = "unresolved"

    total = round((tool_usage + protocol_adherence + error_recovery + efficiency) / 4, 2)

    return RunScore(
        scenario_id=result["scenario_id"], model=result["model"], outcome=outcome,
        tool_usage=tool_usage, error_recovery=error_recovery,
        protocol_adherence=protocol_adherence, efficiency=efficiency,
        total=total, notes=notes,
    )


def score_dict(score: RunScore) -> dict:
    return asdict(score)
