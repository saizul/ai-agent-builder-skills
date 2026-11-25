# Log format and heuristics

## Accepted JSONL

Message per line:

```json
{"conversation_id": "c-1001", "role": "user", "content": "Where is my order?", "timestamp": "2026-11-20T09:12:03Z"}
{"conversation_id": "c-1001", "role": "assistant", "content": "Could you share the order number?"}
{"conversation_id": "c-1001", "role": "tool", "name": "lookup_order", "content": "timeout", "error": true}
{"conversation_id": "c-1001", "role": "assistant", "content": "...", "event": "handover"}
```

Conversation per line:

```json
{"id": "c-1002", "intent": "returns", "handover": false, "messages": [{"role": "user", "content": "..."}]}
```

Roles: `user`; `assistant`, `bot`, `agent`, `ai`, `model`; `human`, `human_agent`, `operator`,
`staff`, `support_agent`; `tool`; `system`. Content may be a string or a list of `{"text": ...}`
parts. Messages are sorted by `timestamp` when every message has one.

## Converting exports

- CSV from a helpdesk: one row per message -> map columns to `conversation_id`, `role`, `content`.
- Platform JSON exports: write a small script that walks conversations and prints one JSON
  object per message. Keep IDs; drop fields you do not need (especially personal data).

## Heuristics used

| Signal | Rule |
| --- | --- |
| Handover | `event` handover/escalation/transfer, a `human` role message, conversation `handover: true` or `resolved_by: human`, or assistant text like "transferring you", "a colleague will reply" |
| assistant_could_not_help | "I can't help", "I don't understand", "could you rephrase", "something went wrong", "I couldn't find" |
| user_frustrated_or_asked_for_human | "talk to a human/person/agent", "real person", "not what I asked", "useless", "???" |
| user_repeated | consecutive user messages more than 80% similar |
| tool_error | tool message with `error` true or containing error / exception / timeout |
| abandoned | last message in the conversation is from the user |

These are English phrase lists. For other languages, extend the regular expressions at the top
of `analyze_logs.py` or provide intent labels and `event` markers from the platform.

## Reading the results

- Handover rate is not bad by itself: correct handovers of out-of-scope requests are success.
  Look at handovers per intent and per trigger.
- Short conversations with abandonment often mean the first answer was slow or off-target.
- Very long conversations (max turns) are often loops; read them first.
