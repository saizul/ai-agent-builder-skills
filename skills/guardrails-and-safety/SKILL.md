---
name: guardrails-and-safety
description: Add practical guardrails to business LLM agents - PII and secret redaction before prompts, logs and indexes; prompt-injection red flags in retrieved documents, web pages, emails and tool results; least-privilege tools and confirmation for write actions; output checks and abuse handling - with a redaction script (emails, phones, Luhn-checked cards, IBANs, SSNs, IPs, credentials; label/mask/hash modes; JSONL aware; allowlist for known-safe values) and an injection scanner (override phrases, fake role markers, exfiltration links, hidden HTML and invisible characters). Use when an agent handles customer data, reads untrusted content (RAG, browsing, email), takes actions, before launch or a security review, or when asked how to make a chatbot safe.
license: MIT
compatibility: Python 3.8+ standard library. Heuristic checks; combine with access control and your LLM provider's or platform's safety features.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Guardrails and safety

Guardrails are layers: limit what the agent can do, keep sensitive data out, treat untrusted
content as data, check outputs, and watch production. No single filter is enough; the scripts
here are tripwires, not proof of safety.

Paths below are relative to this skill's folder.

## When to use

- Agent handles personal data (customers, employees, patients) or payment-related flows
- Agent reads untrusted content: retrieved documents, web pages, emails, uploaded files, tool output
- Agent can act: send messages, change records, refund, book
- Pre-launch security review, or "how do we stop prompt injection / data leaks?"

## When not to use

- General application security (auth, infra, dependencies): use your normal security review
- Content moderation policy design for a social platform: specialised tooling and policy work
- Legal compliance sign-off: involve the data protection / legal owner; this skill supports them

## Workflow

1. **Map the data flows.** For each input (user message, retrieved docs, tool results, files)
   and output (reply, tool call, log, analytics, index): what data, who can see it, where it is
   stored and for how long. Mark untrusted inputs and irreversible outputs.
2. **Limit capability first.** Least-privilege tools (read-only where possible, scoped to the
   authenticated user), confirmation for write actions enforced in code, rate limits, spend
   caps, and a kill switch. See [references/guardrail-layers.md](references/guardrail-layers.md).
3. **Redact PII and secrets** before data goes to logs, analytics, eval sets, indexes or an
   LLM provider that should not receive it.
   ```bash
   python3 scripts/redact_pii.py transcript.txt                     # labels: [EMAIL], [PHONE]...
   python3 scripts/redact_pii.py logs.jsonl --jsonl --mode hash --salt "$REDACT_SALT" --out clean.jsonl
   python3 scripts/redact_pii.py export.csv --check --json          # gate: exit 1 if PII found
   python3 scripts/redact_pii.py notes.txt --only EMAIL,PHONE --pattern 'ORDER=ORD-\d{6}'
   python3 scripts/redact_pii.py logs.txt --allow 'support@example\.com' --allow-file allow.txt
   ```
   `--mode hash` maps the same value to the same token so analytics still work; keep the salt
   secret. The script never prints the values it finds. Regexes miss names and addresses; for
   those, add patterns or a dedicated PII service.
4. **Scan untrusted content for injection** before indexing and, where feasible, at retrieval.
   ```bash
   python3 scripts/injection_scan.py knowledge-base/                # files and folders
   python3 scripts/injection_scan.py chunks.jsonl --jsonl-field text --json
   python3 scripts/injection_scan.py page.html --threshold 3
   ```
   Exit 1 when any item scores at or above `--threshold`. Quarantine flagged items for human
   review; do not silently drop them (you want to know who is attacking). Patterns and their
   limits: [references/injection-patterns.md](references/injection-patterns.md).
5. **Harden the prompt and runtime.** Delimit untrusted content and state that it is data, not
   instructions; never put secrets in prompts; strip or neutralise links and images in model
   output if the channel renders them; validate tool arguments server-side.
6. **Check outputs** for the failures that matter to the business: PII of other users, promises
   (refunds, prices), off-topic content, links to unknown domains. Use `redact_pii.py --check` on
   outputs in eval runs and add safety cases to `eval-harness`.
7. **Monitor and respond.** Log redacted conversations, flag injection hits and refusals, review
   weekly, and keep an incident playbook (disable tool, roll back prompt, notify owner).

## Output

```
Data flows: 4 inputs (2 untrusted: help-center scrape, customer emails), 3 outputs
redact_pii --check on 30-day logs: 1,204 values (EMAIL 812, PHONE 377, CARD 15) -> logs now redacted (hash mode)
injection_scan on 2,310 chunks: 3 suspicious
  kb/faq-shipping.html#12 score=8 override-instructions, hidden-html
Fixes: quarantine 3 chunks, create_refund now requires confirm token, links stripped in SMS channel,
added 6 safety eval cases. Residual risk: names/addresses not detected by regex.
```
