# Tool design rules

## Names

- `verb_object`, lower snake case: `lookup_order`, `list_invoices`, `create_ticket`.
- Consistent verbs: `get` (one by key), `list`/`search` (many), `create`, `update`, `cancel`.
- No two tools with near-identical names or purposes. If they differ, the names should say how
  (`search_orders_by_customer` vs `lookup_order_by_number`).

## Descriptions

Template:

> Look up a single order by order number and the customer's email. Use when the user gives an
> order number; use search_orders when they only have a name or date. Returns status, items,
> shipping carrier and ETA. Read-only.

Include: what, when (and when not), returns, side effects, confirmation needs, limits
("max 50 results"). Avoid marketing words and implementation detail the model cannot use.

## Parameters

| Do | Instead of |
| --- | --- |
| `order_number` (string, "e.g. ORD-123456") | `id`, `data`, `value` |
| `"enum": ["open", "shipped", "delivered"]` | "status: one of open, shipped or delivered" |
| `"type": "integer", "minimum": 1, "maximum": 50` | "a number up to 50" |
| `"format": "date"` + "YYYY-MM-DD" in the description | "the date" |
| `include_archived` (boolean, default false) | `no_archive`, `skip_active` |
| `"required": ["order_number", "email"]` | no required list |
| `"additionalProperties": false` | open objects the model fills with invented keys |
| a nested object with its own properties | `options` as a free-form string of JSON |

Keep the root `type: object`. Keep nesting shallow (max 2-3 levels). Under ~10 parameters per
tool; more usually means two tools.

## Results

- Return only what the model needs to answer or decide the next step. Large payloads cost tokens
  and distract.
- Stable, descriptive keys; include units (`amount_eur`, `eta_date`).
- Errors as data: `{"error": "<machine_code>", "message": "<human hint>", "retryable": false}`.
  Tell the model what to do next ("ask the user for the email used at checkout").
- Paginate: `{"items": [...], "next_cursor": "..."}` and say so in the description.
- Never return secrets, internal hostnames or full personal records the user should not see.

## Write tools

- Idempotency: accept a client-generated key or a natural key so retries do not duplicate.
- Confirmation: enforce in code (prepare/confirm pair, or a `confirmed: true` flag the
  application sets only after the user clicks), not only in the prompt.
- Authorisation: the tool checks that the authenticated user may act on the resource; never
  trust IDs the model passes.
- Audit: log who, what, when and the model's stated reason.

## Example: before and after

Before:

```json
{"name": "orders", "description": "Order tool", "parameters": {"type": "object",
 "properties": {"data": {"type": "string"}, "mode": {"type": "string", "description": "get or cancel"}}}}
```

After:

```json
[
  {"name": "lookup_order",
   "description": "Look up one order by order number and customer email. Use when the user gives an order number. Returns status, items and ETA. Read-only.",
   "parameters": {"type": "object", "additionalProperties": false, "required": ["order_number", "email"],
     "properties": {
       "order_number": {"type": "string", "description": "Order number from the confirmation email, e.g. ORD-123456"},
       "email": {"type": "string", "format": "email", "description": "Email address used at checkout"}}}},
  {"name": "cancel_order",
   "description": "Cancel an order that has not shipped. Call only after the user has confirmed the cancellation summary. Returns the cancellation reference.",
   "parameters": {"type": "object", "additionalProperties": false, "required": ["order_number", "reason"],
     "properties": {
       "order_number": {"type": "string", "description": "Order number, e.g. ORD-123456"},
       "reason": {"type": "string", "enum": ["changed_mind", "ordered_by_mistake", "too_slow", "other"], "description": "Reason the customer gave"}}}}
]
```
