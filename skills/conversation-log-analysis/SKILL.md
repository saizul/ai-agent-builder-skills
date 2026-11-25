---
name: conversation-log-analysis
description: Analyse production chatbot and agent conversation logs to find what to fix next - intent mix (from labels or keyword rules), handover rate overall and per intent, failure turns (assistant could not help, user repeats or asks for a human, frustration, tool errors), abandonment and conversation length - with a script that reads JSONL message or conversation logs, masks emails and phones in examples, and can fail when handover or failure rates exceed thresholds. Use when reviewing a live or pilot agent, preparing a weekly quality report, deciding which intents to add or fix, measuring KPIs from the agent spec, or turning real failures into eval cases.
license: MIT
compatibility: Python 3.8+ standard library. Works with logs exported from any chat platform, helpdesk or agent framework once converted to JSONL.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Conversation log analysis

Production logs show what users really ask and where the agent fails. Review them weekly:
numbers first, then read the worst conversations, then turn findings into fixes and tests.

Paths below are relative to this skill's folder.

## When to use

- "How is our chatbot doing?", weekly or pilot quality reports
- Handover rate too high, CSAT dropped, users complain about loops
- Deciding which intents to automate next or which docs are missing
- Measuring the KPIs in the agent spec (containment, handover, repeat contact)

## When not to use

- Pre-launch testing without real traffic: use `eval-harness`
- Logs contain unredacted personal data you may not process: redact first with
  `guardrails-and-safety` (`redact_pii.py --jsonl`) and confirm you are allowed to analyse them
- Business analytics on revenue or funnels: use your analytics tool

## Workflow

1. **Export and convert** the logs to JSONL: one message per line
   (`conversation_id`, `role`, `content`, optional `timestamp`, `intent`, `event`) or one
   conversation per line (`id`, `messages`, optional `intent`, `handover`). Field details and
   converters: [references/log-format.md](references/log-format.md). Redact before analysis.
2. **Define intents.** Use labels from the platform if present; otherwise write keyword rules
   (`{"order_status": ["where is my order", "tracking"], ...}`) from 50-100 sampled conversations.
   Rules are matched in order on user messages; first match wins.
3. **Run the summary.**
   ```bash
   python3 scripts/analyze_logs.py logs.jsonl
   python3 scripts/analyze_logs.py logs/*.jsonl --intents intents.json --examples 10
   python3 scripts/analyze_logs.py logs.jsonl --json > week-47.json
   python3 scripts/analyze_logs.py logs.jsonl --max-handover-rate 0.3 --max-failure-rate 0.2
   ```
   Exit 1 when a rate exceeds its threshold (use it for alerts).
4. **Read the numbers.** Compare with the KPI targets and last week. Per intent: high share + high
   handover = biggest opportunity; high failure turns = prompt, tool or knowledge gap;
   high abandonment = slow or confusing answers. "unclassified" above ~15% means the intent
   rules need work.
5. **Read conversations.** Open 10-20 failure examples (the script lists IDs and masked snippets)
   and 5 random successful ones. Classify each failure cause: missing knowledge, wrong tool,
   policy gap, prompt rule, UX/channel, out of scope. Heuristics are in
   [references/log-format.md](references/log-format.md).
6. **Act.** For each top cause: the fix (docs, tool, prompt, scope), the owner, and an eval case
   in `eval-harness` that reproduces it. Re-run next week to confirm the trend.

## Output

```
Week 47: 3,412 conversations, 9,870 user turns (mean 2.9, median 2, max 31)
handover 22.4% (target < 30%), failure turns in 18.1%, abandoned 9.7%, tool errors 41
Top intents: order_status 38% (handover 9%), returns 21% (handover 34%), unclassified 12%
Failure reasons: assistant_could_not_help 402, user_repeated 188, user_frustrated_or_asked_for_human 155
Top fixes: 1) returns for marketplace orders not supported -> scope + doc (ops)
           2) lookup_order times out at 09:00-10:00 -> 41 tool errors (backend)
           3) 'unclassified' contains invoice requests -> new intent rule + FAQ
New eval cases: 6 (tag: regression-w47)
```
