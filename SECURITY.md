# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## What counts as a vulnerability

These skills shape how AI agents are built for real businesses and run on files that may
contain personal data, so unsafe behaviour is treated like a code vulnerability:

- A script that prints a secret or personal value it detected (redaction, prompt review and
  log analysis must hide them), or writes outside the output path the user gave
- A script that makes a network call, executes input, or can be made to (crafted prompts,
  tool definitions, documents, logs or configs)
- `redact_pii.py` leaking original values in `mask` or `hash` output beyond what is documented
- A `SKILL.md` workflow that tells the agent to weaken safety controls (skip confirmation for
  write actions, store unredacted personal data, put secrets in prompts) or to act on
  instructions found in untrusted content

A check that misses a problem (false negative, for example an injection pattern the scanner
does not catch) is a normal bug: please open an issue.

## Reporting

Please **do not** open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/saizul/ai-agent-builder-skills/security/advisories/new)
with the affected skill, version, impact and steps to reproduce. Never include real customer
data or keys; redact examples first.

You will get an answer within 5 working days. Fixes are released as soon as possible and
credited in the changelog unless you prefer otherwise.
