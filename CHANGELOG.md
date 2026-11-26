# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `guardrails-and-safety`: `redact_pii.py --allow REGEX` (repeatable) and `--allow-file FILE`
  keep known-safe values such as a public support address, documentation IPs or test cards.
  An allow regex must match the whole detected value; kept values are reported as `allowed`
  counts (never printed) and do not fail `--check`.

## [0.1.0] - 2026-11-25

### Added

- `agent-scoping`: discovery questions, scoping patterns, agent spec template and `spec_lint.py`
  (missing sections, placeholders, write tools without confirmation rules, handover triggers
  without destination, KPIs without numeric targets or measurement).
- `tool-schema-design`: design rules with before/after example and `tool_schema_lint.py` for
  flat and wrapped JSON Schema tool definitions (descriptions, types, ambiguous names, enum
  candidates, unknown required fields, array items, open objects, overlapping and duplicate tools).
- `system-prompt-review`: checklist, prompt skeleton and `prompt_review.py` (contradictions,
  refusal/handover/tool rules, placeholders, dates, secrets, duplicates, vague phrasing, length).
- `rag-ingestion`: chunking guide and `chunk_docs.py` (Markdown/HTML/text, heading paths,
  sentence overlap, code fences kept, exact and near-duplicate detection, size stats, JSONL).
- `eval-harness`: case design guide, check reference, example cases and `run_evals.py`
  (exact, contains, not_contains, one_of, regex, length, JSON field, tool calls, rubric with
  external grades, per-tag pass rates, baseline regressions, CI thresholds).
- `guardrails-and-safety`: guardrail layers, injection patterns, `redact_pii.py` (label, mask,
  hash; JSONL; check mode) and `injection_scan.py` (override phrases, role markers,
  exfiltration links, hidden HTML, invisible characters).
- `cost-latency-estimator`: assumptions guide, example config with placeholder prices and
  `estimate_cost.py` (history growth, tool round trips, caching, routing mix, fixed costs,
  budget, traffic scenarios, token estimates for files).
- `conversation-log-analysis`: log format guide and `analyze_logs.py` (intents, handover,
  failure turns, repeats, tool errors, abandonment, masked examples, thresholds).
- `agent-deployment-checklist`: launch checklist template, launch guide and
  `readiness_check.py` (GO / GO WITH SIGN-OFF / NO-GO, n/a reasons, evidence).
- Claude Code plugin marketplace manifest, `tools/validate_skills.py`, vendor-neutrality test,
  CI and release workflows.

[Unreleased]: https://github.com/saizul/ai-agent-builder-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saizul/ai-agent-builder-skills/releases/tag/v0.1.0
