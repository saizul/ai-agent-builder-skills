# Config fields and assumptions

| Field | Meaning |
| --- | --- |
| `models.<name>.input_per_mtok` | Price per 1M input tokens (your LLM provider's current price) |
| `models.<name>.cached_input_per_mtok` | Price per 1M cached input tokens (omit if no caching: input price is used) |
| `models.<name>.output_per_mtok` | Price per 1M output tokens |
| `models.<name>.ttft_ms` | Typical time to first token, ms (measure it) |
| `models.<name>.output_tokens_per_sec` | Typical output speed |
| `routing` | Share of conversations per model; must sum to 1 |
| `traffic.conversations_per_day`, `days_per_month`, `turns_per_conversation` | Volume |
| `tokens.system_prompt`, `tokens.tool_definitions` | Static tokens sent on every call |
| `tokens.user_message`, `tokens.output` | Average per turn |
| `tokens.retrieved_context` | Retrieved chunks added per turn (0 without RAG) |
| `tokens.history_carryover` | true: each turn resends all previous turns |
| `tokens.tool_calls_per_turn` | Average tool round trips per turn (fractions allowed) |
| `tokens.tool_result`, `tokens.tool_call_tokens` | Tokens per tool result / per tool-call output |
| `caching.cached_fraction_of_static` | Share of static tokens billed at the cached price (0-1) |
| `latency.tool_latency_ms`, `latency.overhead_ms` | Tool execution and network/app overhead per turn |
| `extra_monthly` | Fixed monthly costs (vector database, hosting, monitoring) |
| `budget_monthly` | Optional; exit code 1 when exceeded |

## Formula per turn k (1-based)

```
history_k   = (k - 1) * (user_message + output)        if history_carryover
base_k      = static + user_message + retrieved_context + history_k
calls       = 1 + tool_calls_per_turn
input_k     = base_k * calls + tool_result * t * (t + 1) / 2      (t = tool_calls_per_turn)
cached_k    = static * cached_fraction * calls                       (billed at cached price)
output_k    = output + tool_call_tokens * t
latency_k   = calls * ttft + output_k / speed + t * tool_latency + overhead
```

Turn latency is the same for every turn in this model (history affects cost, not the simple
latency estimate); real time to first token grows with input size, so measure long conversations.

## Typical surprises

- History growth: cost per conversation grows roughly with the square of the number of turns.
- Tool loops: an agent that calls 3 tools per turn pays the full context 4 times.
- Retrieved context: 5 chunks x 400 tokens = 2,000 input tokens on every turn.
- Tool definitions: 20 tools can be several thousand tokens on every call.
- Retries and timeouts: add 5-10% if your runtime retries failed calls.
- Evaluation runs and development traffic: budget them separately.
