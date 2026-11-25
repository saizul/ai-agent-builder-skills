---
name: eval-harness
description: Build a small, business-focused evaluation set for an LLM agent or feature and score recorded outputs against it - test cases per in-scope task, out-of-scope and handover cases, policy and safety cases, tool-selection cases - with a stdlib script that runs JSONL test cases against JSONL outputs using exact, contains, not_contains, one_of, regex, max/min length, JSON field, tool_called and rubric checks, exports rubric items for human or judge grading, reports pass rate per tag and regressions against a baseline, and fails CI below a threshold. Use when the user wants to test an agent, compare prompts or models, prevent regressions, decide if an agent is good enough to launch, or asks how to evaluate a chatbot.
license: MIT
compatibility: Python 3.8+ standard library. The script never calls an LLM; you record outputs with your own runner (any LLM provider or framework).
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Eval harness

Without an eval set, every prompt change is a guess. Start with 30-100 cases that reflect the
business, score them automatically where possible, and run them on every change.

Paths below are relative to this skill's folder.

## When to use

- "How do I test my chatbot / agent?", "is it ready to launch?"
- Comparing two prompts, models, retrieval settings or tool definitions
- Adding a regression gate to CI for prompt or tool changes
- Turning failed production conversations into permanent tests

## When not to use

- No defined scope yet: write the agent spec first (`agent-scoping`)
- Load or latency testing: use a load-testing tool; estimate with `cost-latency-estimator`
- Mining production logs for problems: `conversation-log-analysis` (then convert findings to cases)

## Workflow

1. **Collect cases** from the spec and real traffic. For each in-scope task: typical, edge and
   ambiguous requests; plus out-of-scope, handover, policy (limits, promises), safety (PII,
   prompt injection in documents) and tool-selection cases. Aim for 20-50 per task over time;
   start with 5-10. Patterns are in [references/case-design.md](references/case-design.md).
2. **Write them as JSONL** like [assets/example-cases.jsonl](assets/example-cases.jsonl): `id`,
   `input` (or a `messages` list), `tags`, `checks`. Prefer deterministic checks; use `rubric`
   only for qualities that cannot be checked by text or structure.
3. **Record outputs** with your own runner: send each case to the agent exactly as production
   does and write `{"id", "output", "tool_calls"}` per line to `outputs.jsonl`. Pin model,
   temperature and prompt version; store them next to the outputs.
4. **Score.**
   ```bash
   python3 scripts/run_evals.py cases.jsonl outputs.jsonl
   python3 scripts/run_evals.py cases.jsonl outputs.jsonl --json > results.json
   python3 scripts/run_evals.py cases.jsonl outputs.jsonl --review-out to-grade.jsonl
   python3 scripts/run_evals.py cases.jsonl outputs.jsonl --grades graded.jsonl --min-pass-rate 0.9
   python3 scripts/run_evals.py cases.jsonl new-outputs.jsonl --baseline results.json --fail-on-regression
   python3 scripts/run_evals.py cases.jsonl outputs.jsonl --tag refunds
   ```
   Check types and options: [references/check-types.md](references/check-types.md).
5. **Grade rubric items.** `--review-out` writes ungraded criteria with input and output. Grade
   them by hand, or with a separate judge model whose grades you spot-check (at least 10%);
   fill `pass` with true/false and pass the file with `--grades`.
6. **Read failures, not only the rate.** Group failures by tag and cause (prompt, retrieval,
   tool, policy gap, bad test). Fix bad tests openly; never delete a failing case to pass.
7. **Gate changes.** In CI or before release: `--min-pass-rate` for the overall bar and
   `--fail-on-regression` against the last accepted results. Keep `results.json` per release.

## Decision points

- **Non-determinism**: run flaky cases 3-5 times and require a majority, or lower temperature
  for evaluation runs; record which cases are flaky.
- **Launch bar**: agree with the business owner, e.g. 100% on safety/policy tags, 90%+ overall,
  no regressions. Put it in the spec.
- **Too few cases for a tag** (< 5): treat its pass rate as anecdotal.

## Output

```
48 case(s): 41 pass, 5 fail, 2 needs review, 0 missing output
pass rate 85.4% (of scored cases 89.1%)
  order-status   18/19  95%
  policy          6/8   75%
  refunds         5/7   71%
[FAIL] refund-limit: tool_not_called: tool calls: ['create_refund']
[FAIL] promo-expired: not_contains: found forbidden ['guarantee']
regressions: refund-limit; fixed: status-no-number
Verdict: not ready - policy tag below the 100% bar; refund tool called without limit check.
```
