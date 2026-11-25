---
name: cost-latency-estimator
description: Estimate tokens per turn, cost per conversation, monthly LLM spend and response latency for an agent or LLM feature from traffic and token assumptions - system prompt, tool definitions, retrieved context, history growth, tool-call round trips, prompt caching, model routing mix, fixed infrastructure costs, budget check and traffic scenarios - with a script driven by a configurable price table (no prices built in; you enter your LLM provider's current prices). Use when quoting or budgeting an agent project, choosing between models or architectures, explaining why costs grew, setting rate limits, or checking if a design meets a latency target.
license: MIT
compatibility: Python 3.8+ standard library. Token counts are estimates; verify with your LLM provider's tokenizer and billing data.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Cost and latency estimator

Agent costs are dominated by input tokens that repeat on every call: system prompt, tool
definitions, retrieved context and conversation history. Model them explicitly before
quoting a price or picking an architecture.

Paths below are relative to this skill's folder.

## When to use

- "How much will this chatbot cost per month?", proposals and budgets
- Comparing designs: bigger context vs. retrieval, one large model vs. routing, caching on/off
- "Why did our bill triple?" (history growth, tool loops, retrieved context)
- Checking whether a multi-tool design can meet a response-time target

## When not to use

- Exact billing reconciliation: use your LLM provider's usage reports
- Load testing real latency: measure with real traffic; use this for planning
- Infrastructure sizing for self-hosted models (GPU memory, throughput): different model

## Workflow

1. **Get current prices** from the user or their LLM provider's pricing page: input, output and
   cached-input price per 1M tokens, plus typical time to first token and output speed. Never
   rely on remembered prices; they change. Record the date and source in the config `_note`.
2. **Measure token sizes** of the real prompt, tool definitions and a typical retrieved context:
   ```bash
   python3 scripts/estimate_cost.py --tokens-file prompt.txt --tokens-file tools.json
   ```
   (characters / 4 is a rough estimate; use the provider's tokenizer when precision matters).
3. **Write the config.** Copy [assets/example-config.json](assets/example-config.json) and set
   models, routing shares (sum to 1), traffic, tokens, caching, fixed monthly costs and budget.
   Field meanings are in [references/assumptions.md](references/assumptions.md).
4. **Run the estimate.**
   ```bash
   python3 scripts/estimate_cost.py config.json
   python3 scripts/estimate_cost.py config.json --compare          # 0.5x, 1x, 2x, 5x traffic
   python3 scripts/estimate_cost.py config.json --set traffic.conversations_per_day=5000 \
       --set caching.cached_fraction_of_static=0 --json
   ```
   Exit 1 when the total exceeds `budget_monthly`.
5. **Find the levers.** Re-run with `--set` to see the effect of: shorter system prompt, fewer
   tool definitions per call, smaller `retrieved_context`, `history_carryover=false` (summaries),
   caching, routing more traffic to a smaller model, fewer tool calls per turn. Report the top
   three by saving.
6. **Check latency** per turn against the target (e.g. first token in under 2 s for chat).
   Each tool call adds a model round trip plus tool latency; parallel tool calls or fewer
   steps are usually the fix.
7. **Report with ranges.** State assumptions, the date of the prices, a low/expected/high
   range (traffic scenarios) and what will be measured in the pilot to replace guesses.

## Output

Example with the placeholder prices in `assets/example-config.json`:

```
Assumptions: prices from <provider pricing page, date>, 1,000 conversations/day, 4 turns
  small-model (80%): 0.0094 USD/conversation, 225.12 USD/month; latency per turn 3,008 ms
  large-model (20%): 0.0593 USD/conversation, 355.68 USD/month; latency per turn 5,842 ms
LLM 580.80 + other 130.00 = 710.80 USD/month (budget 1,500: within)
Scenarios: x0.5 420, x2 1,292, x5 3,034 USD/month
Levers (LLM cost): 95% small-model routing -> 356 (-39%); retrieved context 1,500 -> 800 tokens
  -> 455 (-22%); history summaries -> 505 (-13%). Without caching it would be 872 (+50%).
Latency: 0.5 tool calls/turn on large-model gives ~5.8 s per turn; target 4 s -> fewer tool steps.
```
