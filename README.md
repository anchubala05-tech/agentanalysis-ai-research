# Multi-Use-Case Agent Model Comparison

Compares a closed-source model (Gemini, via API — free tier) against an
open-source model (Llama 3.1, via local Ollama) on the SAME agentic loop
across 4 different business problems. No framework (no LangGraph) — a
plain ~100-line ReAct-style loop in `agent_loop.py`, so the full
trajectory is easy to read and reason about.

This repo is Part 2 of the AI Researcher take-home assessment. Part 1's
findings (the research report) and Part 3 (the presentation deck) were
built directly from the trajectory logs this harness produces.

## The 4 use cases (scenarios/)

1. **carrier_rerouting** — Logistics: telemetry alert -> evaluate carriers -> book reroute
2. **incident_response** — Cloud infra: error-rate spike -> check metrics -> rollback/restart
3. **support_ticket** — Customer support: refund request -> check order -> issue refund
4. **inventory_replenishment** — Supply chain: low stock -> check suppliers -> place PO

Each has 2-3 mocked tools that can be made to fail on purpose
(`--fail-rate`), so you can see how each model recovers — or doesn't.

## Headline result

Under a 40% injected tool-failure rate, Llama 3.1 fabricated a completed
refund it never actually issued (`issue_refund` was never successfully
called, yet the model reported "refund issued... no further action
required"). Gemini, facing the same class of failure, accurately reported
"the refund could not be processed... manual intervention is required"
and escalated. Full evidence and analysis: see the Part 1 report,
Section 4.1, and `logs/` for the raw trajectories.

## Setup (conda)

```bash
conda create -n reroute-agent python=3.11 -y
conda activate reroute-agent
pip install -r requirements.txt
```

## Set up the closed-source model — free option (recommended)

No credit card needed. Get a key at [aistudio.google.com](https://aistudio.google.com)
(sign in with Google → "Get API key" → Create key). Google is on the
assignment's approved list of closed-source providers alongside
OpenAI/Anthropic, so this is a legitimate substitution, not a workaround.

Create a `.env` file in this folder (auto-loaded, no need to `export`/`set`):
```
GEMINI_API_KEY=your-key-here
```

**If you do have Claude API budget**, use `--closed-source claude` instead
and add `ANTHROPIC_API_KEY` to `.env`.

## Set up Ollama (the open-source model)

```bash
# install from ollama.com if you haven't already
ollama pull llama3.1
# `ollama serve` is usually already running as a background service on
# Windows/Mac after install -- if you see "address already in use" when
# starting it manually, that's expected, not an error.
```

## Sanity check first (no real models, just the harness)

```bash
python compare_models.py --mock
```
You should see all 4 scenarios run for both slots with no errors. Confirms
the wiring works before you spend real inference time.

## Run the real comparison

```bash
python compare_models.py --closed-source gemini --ollama-model llama3.1
```

Stress-test recovery behavior (tools fail 40% of the time — this is the
run that surfaced the headline finding above):
```bash
python compare_models.py --closed-source gemini --ollama-model llama3.1 --fail-rate 0.4
```

Full trajectories print to the terminal and save to
`logs/comparison_results.json`. A scored summary table prints at the end
and saves to `logs/scores.json` — four 0-2 dimensions per run, computed by
`rubric.py`:

- **tool_usage** — did it call a real tool before deciding, or guess blind
- **protocol_adherence** — valid JSON / valid tool names, no confused responses
- **error_recovery** — how it handled injected tool failures, if any
- **efficiency** — steps taken to reach a decision

**Known rubric limitation** (documented in the Part 1 report, Section 4.2):
efficiency is pure step-count, which can reward under-verification. In
one baseline run, Gemini scored lower on efficiency specifically *because*
it re-checked system state before declaring success, while Llama 3.1
scored higher for skipping that check. Read the `notes` field per score,
not just the number.

## What to look for when comparing

- **Did it call tools in a sensible order**, or jump straight to a decision
  without checking anything?
- **Tool failure recovery**: with `--fail-rate` > 0, does the model retry,
  try an alternative, or give up and escalate cleanly? **Does it ever
  claim an action succeeded when the tool that would perform it was never
  successfully called?** This is the single most important thing to check
  — see the headline result above.
- **JSON discipline**: open-source models, especially smaller ones, are
  more prone to `unparseable_response` or `invalid_tool_name` events.
- **Escalation judgment**: does it correctly recognize when it genuinely
  can't resolve something autonomously, vs. escalating too eagerly or not
  eagerly enough?

## Extending

Add a 5th use case by copying any file in `scenarios/` and changing the
tools/alert/goal — the agent loop and comparison script don't need to
change at all. That's the point of the generic `Scenario` structure in
`scenarios/base.py`.

## Decision log (AI tool usage)

Per the assignment's AI tool policy — how AI assistance was used, what was
accepted/rejected, and which architectural decisions were made by hand.

**Architecture, made by hand:**
- Chose a hand-rolled ~100-line ReAct loop over LangGraph/CrewAI for this
  comparison harness specifically so every trajectory step is transparent
  and directly scorable — a framework would add abstraction between the
  model's actual behavior and what gets logged, which matters when the
  entire point of the exercise is auditing that behavior. (A LangGraph
  version of the underlying rerouting agent was also built, as a separate
  proof-of-concept, before this generalization to 4 use cases.)
- Designed the `Scenario` abstraction (`scenarios/base.py`) so a new
  business use case is pure data (alert text, tools, goal) with zero
  changes to the loop or comparison script — deliberately traded a small
  amount of upfront structure for the ability to add use case 5, 6, 7
  without touching tested code.
- Designed the rubric (`rubric.py`) as rule-based rather than
  LLM-as-judge, trading generality for determinism and auditability in a
  benchmarking context where reproducibility matters more than nuance.

**Real bugs found and fixed through testing, not assumed correct:**
- LangGraph (in the earlier single-use-case version) silently drops any
  state key not declared in the `TypedDict` schema — caught by testing,
  not by reading docs; fixed by using closure variables instead of
  smuggling objects through state.
- The mock carrier API's "empty result, no exception" failure mode wasn't
  incrementing the retry counter, which could cause an unbounded retry
  loop. Caught by stress-testing across multiple seeds before trusting
  the happy-path run.
- Gemini's actual current model identifier (`gemini-flash-lite-latest`)
  differs from what any training-data-based assumption would produce —
  confirmed against live API behavior (a 404) rather than guessed, and
  the working alias is used specifically because it auto-updates rather
  than hard-coding a dated model string.

**The headline finding was verified, not assumed:**
- The "fabricated success" result (Section 4.1 of the Part 1 report) was
  confirmed by reading the raw trajectory JSON line by line, not by
  trusting the automated rubric score alone. The rubric flagged
  `error_recovery=0` on that run as anomalous; the actual trajectory was
  then inspected to understand *why*, which is what surfaced the
  specific claim ("refund issued") with no corresponding successful tool
  call anywhere in the log. This is deliberately called out because it's
  the difference between reporting a number and reporting a finding.

**Scope decisions:**
- Llama 3.1 8B (not a larger/newer open-source model) was used because it
  runs on consumer hardware via Ollama with zero cloud dependency — a
  practical constraint for this assessment. The report explicitly notes
  this is not a claim about open-source capability in general, and names
  Qwen3.6 / GLM-5.2 as stronger current alternatives worth a follow-up
  evaluation.
- Sample size is 4 scenarios x 1 run per condition. This is stated as a
  limitation in the report rather than presented as statistically
  validated — a larger n (multiple seeds per scenario) is the natural
  next step, not a gap that was hidden.
