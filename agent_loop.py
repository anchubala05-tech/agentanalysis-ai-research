"""
A minimal ReAct-style loop: the model sees the alert + available tools,
responds with JSON choosing either "call_tool" or "final_decision", we
execute the tool if asked and feed the result back, repeat up to
MAX_STEPS times. This is intentionally simple (no framework) so the
full trajectory is transparent and easy to score.

The `trajectory` list this produces is the artifact both parts of the
assignment care about: Part 2 needs it to prove the agent acts
autonomously and recovers from failures; Part 1's rubric scores it.
"""

import json
from scenarios.base import Scenario, tool_menu_text
from providers.llm_providers import ModelProvider

MAX_STEPS = 6

SYSTEM_TEMPLATE = """You are an autonomous {domain} agent.

GOAL: {goal}

You have access to these tools:
{tools}

On each turn, respond with ONLY a JSON object, no other text, in one of these two forms:
1. To call a tool: {{"thought": "...", "action": "call_tool", "tool": "<tool_name>", "args": {{...}}}}
2. To finish:      {{"thought": "...", "action": "final_decision", "decision": "<what you decided and why>"}}

If a tool call fails, you will see the error and should decide whether to retry,
try a different approach, or (if truly stuck) finish with a decision to escalate
to a human, explaining why."""


def run_agent(scenario: Scenario, provider: ModelProvider) -> dict:
    tools_by_name = {t.name: t for t in scenario.tools}
    system_prompt = SYSTEM_TEMPLATE.format(
        domain=scenario.business_domain, goal=scenario.goal,
        tools=tool_menu_text(scenario.tools),
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Incoming alert: {scenario.alert_text}"},
    ]

    trajectory = []
    final_decision = None
    escalated = False

    for step in range(MAX_STEPS):
        raw = provider.chat(messages)
        messages.append({"role": "assistant", "content": raw})

        parsed = _safe_parse(raw)
        if parsed is None:
            trajectory.append({"step": step, "event": "unparseable_response", "raw": raw})
            messages.append({"role": "user", "content": "Your last response wasn't valid JSON. Respond with ONLY the JSON object."})
            continue

        action = parsed.get("action")

        if action == "final_decision":
            final_decision = parsed.get("decision", "")
            trajectory.append({"step": step, "event": "final_decision",
                                "thought": parsed.get("thought"), "decision": final_decision})
            escalated = "escalat" in final_decision.lower() or "human" in final_decision.lower()
            break

        elif action == "call_tool":
            tool_name = parsed.get("tool")
            args = parsed.get("args", {})
            tool = tools_by_name.get(tool_name)

            if tool is None:
                trajectory.append({"step": step, "event": "invalid_tool_name", "requested": tool_name})
                messages.append({"role": "user", "content": f"Tool '{tool_name}' doesn't exist. Available tools: {list(tools_by_name)}"})
                continue

            try:
                result = tool.func(args)
                trajectory.append({"step": step, "event": "tool_call_success", "tool": tool_name,
                                    "args": args, "result": result})
                messages.append({"role": "user", "content": f"Tool result: {json.dumps(result)}"})
            except Exception as e:
                trajectory.append({"step": step, "event": "tool_call_error", "tool": tool_name,
                                    "args": args, "error": str(e)})
                messages.append({"role": "user", "content": f"Tool error: {e}. You may retry, try another tool, or escalate if stuck."})
        else:
            trajectory.append({"step": step, "event": "unknown_action", "raw": parsed})
            messages.append({"role": "user", "content": "Unrecognized action. Use 'call_tool' or 'final_decision'."})

    else:
        trajectory.append({"step": MAX_STEPS, "event": "max_steps_exhausted"})
        escalated = True

    return {
        "scenario_id": scenario.id,
        "model": provider.name,
        "trajectory": trajectory,
        "final_decision": final_decision,
        "escalated": escalated,
        "steps_taken": len(trajectory),
    }


def _safe_parse(raw: str):
    raw = raw.strip()
    # Models sometimes wrap JSON in ```json fences despite instructions -- strip if present.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
