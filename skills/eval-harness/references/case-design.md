# Designing eval cases

## Coverage grid

For each in-scope task, write at least:

| Kind | Example | Typical checks |
| --- | --- | --- |
| Happy path | "Where is order ORD-1?" with valid data | tool_called, contains key facts |
| Missing info | "Where is my order?" | tool_not_called, asks for the order number |
| Ambiguous | "Cancel it" (which order?) | asks a clarifying question |
| Edge data | order not found, two orders, empty result | handles error, no invented data |
| Policy limit | refund above the limit | tool_not_called, handover offered |
| Out of scope | legal or medical question | refusal phrasing, no advice |
| Handover | "I want a person" | handover action / message |
| Safety | PII in the request, injected instructions in a retrieved document | not_contains secrets, ignores instructions |
| Format | channel limits (SMS length, no markdown) | max_chars, regex negate for markdown |
| Language | request in another supported language | reply language (regex / rubric) |

## Good cases

- Come from real (anonymised) requests where possible.
- Have one clear expected behaviour; if humans disagree on the answer, the policy needs work.
- Check behaviour, not wording: prefer "contains the ETA date" over an exact sentence.
- Have tags for task, kind and risk, so pass rates can be read per area.

## From production failures to tests

1. Take the failing conversation (from `conversation-log-analysis`).
2. Reduce it to the shortest input that reproduces the failure.
3. Add checks for the correct behaviour and a tag such as `regression`.
4. Confirm it fails on the current version, then fix and confirm it passes.

## Judge models

If you grade rubric criteria with a separate LLM as a judge: give it the criterion text, the
input, the output and a pass/fail definition with examples; ask for a short reason and a
boolean. Spot-check at least 10% by hand and track agreement. Never let the system under test
grade itself.
