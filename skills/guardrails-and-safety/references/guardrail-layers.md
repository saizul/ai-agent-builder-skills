# Guardrail layers

| Layer | Controls | Notes |
| --- | --- | --- |
| Capability | Read-only tools by default; scoped credentials; per-user authorisation in every tool; no generic "run SQL" / "fetch any URL" tools | The strongest control: what the agent cannot do, it cannot be tricked into doing |
| Confirmation | Prepare/confirm pairs or UI confirmation for write actions; amount limits; human approval queue for high value | Enforced in code, not only in the prompt |
| Input | Redact PII/secrets; injection scan of untrusted content; size limits; file type allowlist | Heuristics: log and review hits |
| Prompt | Clear scope and refusal rules; untrusted content delimited and labelled as data; no secrets | See `system-prompt-review` |
| Output | PII check, policy phrases ("guaranteed", "refund approved"), link/domain allowlist, length limits, format validation (JSON schema) | Block, rewrite or hand over |
| Runtime | Rate limits per user and IP, spend caps, timeouts, max tool calls per turn, kill switch | Protects cost and availability |
| Monitoring | Redacted logs, injection/refusal/handover dashboards, sampled human review, incident playbook | You cannot fix what you do not see |

## PII policy questions

- Which personal data does the agent need for each task? Collect only that.
- Which LLM provider, region and data-retention settings apply? Is a data processing agreement in place?
- How long are conversation logs kept? Who can read them?
- How does a user request deletion of their data, including logs and eval sets?
- Are eval sets and analytics built from redacted data only?

## Write-action safety

- Show a summary (what, amount, recipient) and require an explicit yes.
- Idempotency keys to stop duplicates on retries.
- Limits per action and per day; above the limit, hand over.
- Audit log with user, action, arguments, model reasoning summary and result.
- A way to undo, or a clear statement that the action cannot be undone.
