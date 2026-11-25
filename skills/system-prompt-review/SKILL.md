---
name: system-prompt-review
description: Review and tighten system prompts for business agents and LLM features - role and scope, refusal rules for out-of-scope requests, handover-to-human rules, tool-use rules, answer format, grounding, tone - with a checklist and a script that flags always/never contradictions, missing refusal or handover rules, tools without usage rules, unfilled placeholders, hard-coded dates, credential-like strings, duplicates, vague phrasing and prompts that exceed a token budget. Use when writing, reviewing or debugging a system prompt, when an agent ignores rules or contradicts itself, before launch, or when a prompt has grown by patching.
license: MIT
compatibility: Python 3.8+ for the review script. Provider-neutral; token counts are estimates (characters / 4).
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# System prompt review

A good business-agent prompt is short, structured, specific and free of conflicts. Review it
like code: automated checks first, then a human read against the checklist, then evals.

Paths below are relative to this skill's folder.

## When to use

- "Review my system prompt", "why does the bot ignore rule X?", "make this prompt better"
- A prompt that grew by patching ("ALWAYS do Y" added after each incident)
- Before a launch or after changing tools, policies or the model
- Converting an agent spec into a first prompt

## When not to use

- No spec yet (scope, handover, out-of-scope unknown): run `agent-scoping` first
- Problems with tool selection or arguments: run `tool-schema-design`
- Measuring whether a change helped: use `eval-harness` (do it after this review)

## Workflow

1. **Get the full prompt** as sent at runtime (with variables filled), plus the tool list and
   the agent spec if they exist. Ask for 3-5 conversations where it went wrong.
2. **Run the automated review.**
   ```bash
   python3 scripts/prompt_review.py prompt.txt
   python3 scripts/prompt_review.py prompt.txt --max-tokens 1500 --tools yes --json
   python3 scripts/prompt_review.py prompt.txt --fail-on medium   # stricter CI gate
   ```
   Exit 1 when findings at or above `--fail-on` (default `high`). Contradiction findings are
   candidates: read both sentences and decide whether they really conflict.
3. **Read it against the checklist** in [references/checklist.md](references/checklist.md):
   role and audience, scope and refusals, handover, tools, grounding and "I don't know",
   format, tone, safety, examples, structure. Note each gap with the line it concerns.
4. **Restructure if needed.** Use the skeleton in
   [references/prompt-skeleton.md](references/prompt-skeleton.md): role, context, scope,
   rules, tools, handover, format, examples. Keep facts that change (prices, stock, dates,
   policies) out of the prompt; fetch them with tools or retrieval.
5. **Resolve conflicts explicitly.** For every contradiction, write which rule wins and when
   ("If the user asks for a refund above 100 EUR, do not process it; hand over"). Remove
   duplicate and vague rules; replace "be helpful" with observable behaviour.
6. **Propose the revised prompt** as a diff, with one line per change explaining why. Do not
   change business rules on your own; list them as questions for the owner.
7. **Verify with evals.** Re-run the eval set (`eval-harness`) on the old and new prompt and
   compare pass rates and regressions before shipping.

## Decision points

- **Over budget** (default ~2500 estimated tokens): move reference material to retrieval,
  examples to a few short ones, policy detail to tool results.
- **Many ALWAYS/NEVER in capitals**: usually a sign of patched incidents; consolidate into a
  short rules list with priorities.
- **Rules the model keeps breaking**: check if a tool or code can enforce it (e.g. confirmation
  before write actions) instead of adding more prompt text.

## Output

```
prompt.txt: 1,940 words, ~2,610 tokens (budget 2,500)
[HIGH]   possible conflicting rules about: refund, process
         'Always process refunds the customer asks for.' vs 'Never process refunds above 100 EUR.'
[HIGH]   no handover/escalation rule
[MEDIUM] hard-coded date: "Today is 2026-03-01"
[LOW]    4 vague phrases: as needed, be helpful, try to
Checklist gaps: no "I don't know" rule, no answer length guidance.
Proposed diff: 14 lines removed, 9 added (see below). Questions for owner: refund limit?
```
