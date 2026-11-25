---
name: agent-deployment-checklist
description: Run a go/no-go launch review for an AI agent or LLM feature - ownership and sign-off, eval results and regressions, safety and privacy controls, handover path, kill switch and rollback, timeouts and fallbacks, rate limits and spend caps, monitoring and alerts, pilot and rollout plan - using a fill-in Markdown checklist with BLOCKER/MAJOR/MINOR items and a script that scores it, requires reasons for n/a and optional evidence for blockers, and returns GO, GO WITH SIGN-OFF or NO-GO. Use when asked whether an agent is ready to ship, before a pilot or production launch, before expanding traffic, or after a major prompt, model or tool change.
license: MIT
compatibility: Python 3.8+ standard library for the scoring script. Platform- and provider-neutral.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Agent deployment checklist

A launch decision should be boring: a checklist with evidence, a clear owner, and a way to turn
the agent off. This skill produces that decision and the list of what is still open.

Paths below are relative to this skill's folder.

## When to use

- "Are we ready to launch the bot?", pilot or production go-live
- Expanding from pilot to more traffic, channels or languages
- After changing the model, prompt, tools or knowledge base significantly
- Post-incident review: which control was missing

## When not to use

- Early design: use `agent-scoping` first; the checklist assumes a spec exists
- Detailed security testing: run `guardrails-and-safety` and your security process; record the
  results here as evidence

## Workflow

1. **Copy the checklist** [assets/launch-checklist.md](assets/launch-checklist.md) to the project
   (e.g. `docs/launch-checklist.md`). Add project-specific items with a severity tag; do not
   delete items, mark them `[~]` with `(n/a: reason)`.
2. **Collect evidence** for each item: eval results (`eval-harness --json`), cost estimate
   (`cost-latency-estimator`), log dashboards, test tickets. Ask the owners; do not tick items
   on assumption. Put links after `-- evidence:`.
3. **Score it.**
   ```bash
   python3 scripts/readiness_check.py docs/launch-checklist.md
   python3 scripts/readiness_check.py docs/launch-checklist.md --require-evidence
   python3 scripts/readiness_check.py docs/launch-checklist.md --json --allow-major
   ```
   Any open BLOCKER = NO-GO. Open MAJOR items = GO WITH SIGN-OFF (exit 1 unless `--allow-major`).
   `[~]` without a reason counts as open.
4. **Review open items** with the owner: for each, fix now, accept with a dated follow-up and a
   named owner, or block. Severity guidance and the pilot plan are in
   [references/launch-guide.md](references/launch-guide.md).
5. **Write the decision** (below) and store it with the checklist in the repository.
6. **After launch**: check the dashboard daily in the first week, run `conversation-log-analysis`
   weekly, and re-run this checklist before each traffic expansion.

## Output

```
Decision: GO WITH SIGN-OFF (pilot, 10% web chat, business hours)
28/31 applicable items done (90%), 2 n/a
  open [MAJOR] line 41 (Monitoring): Alerts on error rate, latency, spend ... -> owner Ops, due 2026-12-02
  open [MAJOR] line 33 (Reliability and cost): Rate limits per user/IP ... -> accepted for pilot (low traffic)
Evidence: eval run 2026-11-24 (93.8%, no regressions), kill switch test ticket OPS-123
Sign-off: <business owner>, <tech lead>, <date>
Next review: before expanding to 50% traffic
```
