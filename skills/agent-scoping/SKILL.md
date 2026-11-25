---
name: agent-scoping
description: Turn a business process into a buildable AI agent spec - goal, users and channels, in-scope tasks, explicit out-of-scope list, tools with read/write access and confirmation rules, handover-to-human triggers, guardrails, KPIs with baselines and numeric targets, evaluation plan, risks and rollout - using a fill-in template and a linter that flags missing sections, placeholders, write tools without confirmation rules and KPIs without targets. Use when a client or team says "we want an AI agent / chatbot / assistant for X", when estimating or proposing an agent project, when a requirements doc is vague, or before writing any prompts or tools.
license: MIT
compatibility: Python 3.8+ for the linter. Works with any LLM provider or agent framework.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Agent scoping

Goal: a one-to-three page spec that a developer can build, a tester can test and a business
owner can sign. Most failed agent projects fail here: no out-of-scope list, no handover rules,
no measurable target.

Paths below are relative to this skill's folder.

## When to use

- "We want an AI agent that handles customer support / bookings / lead qualification / invoices"
- Writing a proposal or estimate for an agent or LLM feature
- A requirements document exists but nobody can say when the agent should hand over
- Reviewing an existing agent that "does too much" or has no success metric

## When not to use

- The spec exists and the question is about prompt wording: use `system-prompt-review`
- Designing individual tool schemas: use `tool-schema-design`
- The process is not repetitive or has no clear owner: say so; an agent will not fix that

## Workflow

1. **Interview before writing.** Ask the questions in
   [references/discovery-questions.md](references/discovery-questions.md), grouped as: process
   today, volume, systems and data, risk, success. Do not invent answers; mark unknowns as
   open questions. Get 5-10 real example requests (anonymised) per task.
2. **Map the process.** Write the current steps as a numbered list: trigger, inputs, decisions,
   systems touched, outputs, who does it. Mark each step as *automate*, *assist* (agent drafts,
   human approves) or *keep human*. See the decision table in
   [references/scoping-patterns.md](references/scoping-patterns.md).
3. **Cut the first version small.** Pick the 2-4 highest-volume, lowest-risk tasks. Everything
   else goes to "Out of scope" with a handover rule. A narrow agent that works beats a broad one
   that guesses.
4. **Fill the template.** Copy [assets/agent-spec-template.md](assets/agent-spec-template.md)
   to the project (e.g. `docs/agent-spec.md`) and fill every section:
   - Tools table: one row per capability, `read` or `write`, and for every write/act tool
     whether the user must confirm first (default: yes for anything that moves money, sends
     messages, deletes or changes records).
   - Handover table: trigger, destination, channel, what context is passed. Always include
     "user asks for a human", "agent fails twice", and every out-of-scope category with risk.
   - KPIs: baseline, numeric target, how it is measured, and by when. At least one quality KPI
     (CSAT, accuracy), one efficiency KPI (containment, handle time), one cost KPI.
5. **Lint the spec.**
   ```bash
   python3 scripts/spec_lint.py docs/agent-spec.md
   python3 scripts/spec_lint.py docs/agent-spec.md --json
   python3 scripts/spec_lint.py docs/agent-spec.md --allow-major   # only blockers fail
   ```
   Fix every `BLOCKER`; resolve or consciously accept each `MAJOR`. Exit code 1 means gaps.
6. **Sanity-check cost and effort.** Rough token and monthly cost with `cost-latency-estimator`;
   effort and risk with the checklist in [references/scoping-patterns.md](references/scoping-patterns.md).
7. **Review with the business owner.** Walk through out-of-scope, handover and KPIs line by line;
   those are the parts people disagree about later. Record sign-off (name, date) in the spec.

## Decision points

- **No system of record for a task** (answers live in people's heads): scope a knowledge-base
  project first, or make the task *assist* only.
- **Write actions with money or legal impact**: require confirmation and a human approval queue
  for the pilot; revisit after the evaluation data is in.
- **Volume under ~20 requests a day**: a template, form or FAQ may beat an agent; say so.
- **Regulated data** (health, finance, children): add the compliance owner to sign-off and
  run `guardrails-and-safety` before the build.

## Output

- The filled spec file, plus a short summary:

```
Agent: Returns & order-status assistant (web chat), v0.1 pilot
In scope: order status, return eligibility, create return (confirm first)
Out of scope (handover): refunds > 100 EUR, damaged-item claims, account changes
Tools: lookup_order (read), check_return_policy (read), create_return (write, confirm)
KPIs: containment 40% by week 8, CSAT >= 4.2, handover < 30%, cost < 0.15/conv
spec_lint: READY (0 blockers, 0 major, 2 minor)
Open questions: marketplace orders? weekend handover queue?
```
