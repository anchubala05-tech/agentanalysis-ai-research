"""
A Scenario bundles: the situation description (what alert came in), the
tools the agent can call to investigate/act, and a success check.

Every use case file (carrier_rerouting.py, incident_response.py, etc.)
builds one of these. The agent loop only knows about this generic shape --
it has no idea whether it's rerouting a truck or restarting a server.
That's the whole trick to comparing models fairly across 4 different
business problems with one harness.
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str          # shown to the model so it knows when to call this
    func: Callable[[dict], dict]   # takes args dict, returns result dict (or raises)


@dataclass
class Scenario:
    id: str
    business_domain: str
    alert_text: str           # the incoming trigger, in plain language
    goal: str                 # what the agent is supposed to accomplish
    tools: list[Tool]
    fail_rate: float = 0.0    # probability any tool call raises an exception this run


def tool_menu_text(tools: list[Tool]) -> str:
    return "\n".join(f"- {t.name}: {t.description}" for t in tools)
