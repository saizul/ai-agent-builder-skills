---
name: tool-schema-design
description: Design and review tool (function-calling) definitions that LLM agents call reliably - verb-object names, descriptions that say what, when and what it returns, typed parameters with descriptions, enums instead of prose lists, correct required fields, closed objects, small focused tools, clear error results - with a linter for JSON Schema tool definitions that flags missing descriptions, ambiguous parameter names, enum candidates, unknown required fields, missing types, array items, overlapping tools and duplicates. Use when writing or reviewing tools/functions for an agent, when the model calls the wrong tool or invents arguments, or when wrapping an internal API as agent tools.
license: MIT
compatibility: Python 3.8+ for the linter. Accepts flat or wrapped tool definitions with a JSON Schema parameters object; works with any LLM provider.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Tool schema design

The model only sees the tool name, description and parameter schema. Treat them as the user
interface for the model: precise, unambiguous, and tested.

Paths below are relative to this skill's folder.

## When to use

- Writing new tools/functions for an agent, or exposing an internal API as tools
- "The model picks the wrong tool", "it makes up arguments", "it never calls X"
- Reviewing a pull request that changes tool definitions
- Consolidating dozens of endpoint-shaped tools into fewer task-shaped ones

## When not to use

- Designing the public HTTP API itself (that is API design, not tool design)
- Prompt wording outside the tool definitions: use `system-prompt-review`
- Deciding which tools the agent should have at all: start with `agent-scoping`

## Workflow

1. **List the tasks, not the endpoints.** From the agent spec, write the user-level actions
   (e.g. "find an order for this customer"). One tool per action; merge endpoints that are
   always called together; split tools whose behaviour depends on a mode flag.
2. **Write each definition** following [references/design-rules.md](references/design-rules.md):
   - Name: `verb_object` (`lookup_order`, `create_return`), unique, no generic `do_action`.
   - Description: what it does, when to use it (and when not to), what it returns, side effects
     and whether the user must confirm first. 1-4 sentences.
   - Parameters: `type` and `description` on every property, formats and examples in the
     description, `enum` for fixed sets, `minimum`/`maximum` for ranges, `required` listing the
     mandatory ones, `"additionalProperties": false`.
   - Write tools: idempotency key or natural key, dry-run/preview option when actions are costly.
3. **Lint the definitions.**
   ```bash
   python3 scripts/tool_schema_lint.py tools.json
   python3 scripts/tool_schema_lint.py tools/*.json --json
   python3 scripts/tool_schema_lint.py tools.json --fail-on high --min-severity low
   ```
   Input can be one tool, a list, or `{"tools": [...]}`; flat (`name`, `description`,
   `parameters`/`input_schema`/`inputSchema`) or wrapped (`{"type": "function", "function": {...}}`).
   Exit 1 when findings at or above `--fail-on` (default `medium`) exist. Add it to CI.
4. **Design the results too.** Return compact JSON with only the fields the model needs, stable
   keys, and actionable errors (`{"error": "order_not_found", "hint": "ask for the order number
   from the confirmation email"}`), never stack traces. See the results section in
   [references/design-rules.md](references/design-rules.md).
5. **Test tool selection.** Write 3-5 eval cases per tool (should call / should not call / needs
   clarification) with `tool_called` / `tool_not_called` checks in `eval-harness`. Overlapping
   tools flagged by the linter are the first suspects when selection fails.
6. **Show the diff** of the improved definitions and explain each change in one line.

## Decision points

- **More than ~15-20 tools**: group by task, load tool subsets per conversation stage, or add a
  routing step; long tool lists reduce selection accuracy.
- **Free-text parameter that is really a choice**: make it an `enum`; if the set is large or
  changes often, add a search/lookup tool instead.
- **The model must not see raw IDs**: accept natural keys (order number + email) and resolve
  them server-side.
- **Dangerous actions**: split into `prepare_x` (returns a summary) and `confirm_x` (requires the
  token from prepare) so confirmation is enforced in code, not only in the prompt.

## Output

```
tools.json: 6 tools, 9 findings (2 high, 4 medium, 3 low)
[HIGH]   create_refund: 'required' lists 'order_id' which is not a property
[HIGH]   helper: tool has no description
[MEDIUM] search_orders .status: description lists allowed values; use 'enum'
[MEDIUM] lookup_order, get_order: descriptions are 71% similar; say how they differ
Proposed: merge get_order into lookup_order, rename helper -> check_return_eligibility,
add enum ["open","shipped","delivered","returned"], fix required -> ["order_number"].
```
