# ai-agent-builder-skills

[![CI](https://github.com/saizul/ai-agent-builder-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/ai-agent-builder-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/saizul/ai-agent-builder-skills?sort=semver)](https://github.com/saizul/ai-agent-builder-skills/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/saizul/ai-agent-builder-skills?style=social)](https://github.com/saizul/ai-agent-builder-skills/stargazers)

**Agent Skills for people who build AI agents and LLM features for businesses: scope it, design the tools, review the prompt, ingest the docs, test it, guard it, cost it, ship it.**

Nine vendor-neutral skills that cover the work around the model: turning a business process
into a spec, writing tool definitions the model calls correctly, catching contradictions in
system prompts, chunking knowledge bases, scoring evals, redacting PII, spotting prompt
injection, estimating monthly cost, analysing production chat logs and making the launch call.
Each skill is a step-by-step workflow plus a tested, standard-library-only Python script, so
your coding agent gets deterministic answers instead of guessing.

- **Vendor-neutral.** No LLM provider, model, framework or vector database is assumed. Prices
  are never built in: you enter your LLM provider's current prices in a config file.
- **Offline and read-only.** No script calls an LLM or the network. They read files and print
  reports; secrets and personal data found are never echoed.
- **Tested.** 100+ tests with fixtures, run on Python 3.11-3.13 in CI.
- **No dependencies.** Python 3.8+ standard library only. Copy a script anywhere and run it.

## Skills

| Skill | What it does | Try asking |
| --- | --- | --- |
| [agent-scoping](skills/agent-scoping/SKILL.md) | Discovery questions, process mapping and a spec template (goal, scope, out-of-scope, tools, handover rules, KPIs, evals, rollout); linter flags missing sections, write tools without confirmation rules, KPIs without numeric targets | "A client wants an AI agent for returns and order status. Write the spec." |
| [tool-schema-design](skills/tool-schema-design/SKILL.md) | Rules for tool/function definitions; linter for JSON Schema tools: missing descriptions, ambiguous params, enum candidates, unknown `required`, missing types and items, overlapping or duplicate tools | "Our agent keeps calling the wrong tool. Review tools.json." |
| [system-prompt-review](skills/system-prompt-review/SKILL.md) | Checklist and skeleton; script flags always/never contradictions, missing refusal and handover rules, tools without usage rules, placeholders, hard-coded dates, secrets, vague and duplicated rules, token budget | "Review this system prompt before we launch." |
| [rag-ingestion](skills/rag-ingestion/SKILL.md) | Source inventory, cleaning, heading-aware chunking with overlap, metadata, dedup, retrieval smoke test; script chunks Markdown/HTML/text to JSONL with stats | "Chunk our help center export for the knowledge base and tell me what's wrong with it." |
| [eval-harness](skills/eval-harness/SKILL.md) | Case design grid; script scores JSONL cases against recorded outputs (exact, contains, regex, JSON field, tool called, rubric with human/judge grades), per-tag pass rates, regressions, CI gate | "Build an eval set for the support bot and tell me if v2 regressed." |
| [guardrails-and-safety](skills/guardrails-and-safety/SKILL.md) | Guardrail layers; PII/secret redaction (Luhn cards, IBANs, phones, emails, SSNs, IPs; label/mask/hash; JSONL) and prompt-injection scanner for retrieved content | "Redact these chat logs and check the scraped pages for injected instructions." |
| [cost-latency-estimator](skills/cost-latency-estimator/SKILL.md) | Tokens per turn, cost per conversation and per month, latency per turn from traffic assumptions, caching, routing mix, tool calls, budget check, traffic scenarios | "What will 2,000 conversations a day cost with RAG and two tools?" |
| [conversation-log-analysis](skills/conversation-log-analysis/SKILL.md) | Intents, handover rate (overall and per intent), failure turns, repeats, frustration, tool errors, abandonment from JSONL chat logs; masked examples; alert thresholds | "Summarise last week's bot conversations and tell me what to fix first." |
| [agent-deployment-checklist](skills/agent-deployment-checklist/SKILL.md) | 30+ item launch checklist (BLOCKER/MAJOR/MINOR) with evidence; script returns GO, GO WITH SIGN-OFF or NO-GO | "Are we ready to pilot the agent next week?" |

## Install

### Claude Code: plugin marketplace (recommended)

```text
/plugin marketplace add saizul/ai-agent-builder-skills
/plugin install ai-agent-builder-skills@ai-agent-builder-skills
```

Or from your shell:

```bash
claude plugin marketplace add saizul/ai-agent-builder-skills
claude plugin install ai-agent-builder-skills@ai-agent-builder-skills
```

Plugin skills are namespaced, e.g. `/ai-agent-builder-skills:eval-harness`. Claude Code also
picks them up automatically when your request matches a skill's description. Update later with
`/plugin marketplace update ai-agent-builder-skills`.

### Claude Code: copy the skills

```bash
git clone https://github.com/saizul/ai-agent-builder-skills.git
# all projects (personal skills)
mkdir -p ~/.claude/skills && cp -r ai-agent-builder-skills/skills/* ~/.claude/skills/
# or just one project
mkdir -p .claude/skills && cp -r ai-agent-builder-skills/skills/eval-harness .claude/skills/
```

Each release also has one zip per skill and an all-skills zip under
[Releases](https://github.com/saizul/ai-agent-builder-skills/releases).

### Codex CLI

Codex reads skills from `~/.agents/skills` (all repositories) and `.agents/skills` in a
repository (from the current directory up to the repository root):

```bash
git clone https://github.com/saizul/ai-agent-builder-skills.git
mkdir -p ~/.agents/skills && cp -r ai-agent-builder-skills/skills/* ~/.agents/skills/
```

Codex also ships a `$skill-installer` skill that can install skills from a GitHub repository;
ask it to install from `saizul/ai-agent-builder-skills`. Skill locations and the installer are
described in the [Codex skills documentation](https://developers.openai.com/codex/skills);
check it if your Codex version behaves differently. [AGENTS.md](AGENTS.md) explains how
Codex and other agents should use these skills.

### Any other agent

The skills follow the open [Agent Skills format](https://agentskills.io/specification):
a folder with `SKILL.md` (YAML frontmatter + instructions), `scripts/`, `references/` and
`assets/`. Point your agent at the folder, or run the scripts yourself; every script has `--help`.

## Usage examples

```text
> We're building a WhatsApp assistant for a dental clinic: bookings, opening hours, prices.
  Scope it.
  (agent-scoping asks the discovery questions, cuts v1 to bookings + FAQ, fills the spec
   template with handover rules for medical questions, then runs spec_lint.py until READY.)

> tools.json and prompt.txt are in ./agent. Why does it refund without asking?
  (system-prompt-review finds "Always process refunds" vs "Never process refunds above
   100 EUR"; tool-schema-design finds create_refund's amount has no type and no range, and
   proposes a prepare/confirm pair so confirmation is enforced in code.)

> Compare outputs-v1.jsonl and outputs-v2.jsonl on our eval set.
  (eval-harness scores both, lists the 3 regressions by tag and exports 6 rubric items
   for human grading.)
```

Run the scripts directly too:

```bash
python3 skills/tool-schema-design/scripts/tool_schema_lint.py tools.json
python3 skills/system-prompt-review/scripts/prompt_review.py prompt.txt --max-tokens 1500
python3 skills/rag-ingestion/scripts/chunk_docs.py docs/ --max-tokens 400 --overlap 50 --dedup --out chunks.jsonl
python3 skills/eval-harness/scripts/run_evals.py cases.jsonl outputs.jsonl --min-pass-rate 0.9
python3 skills/guardrails-and-safety/scripts/redact_pii.py logs.jsonl --jsonl --mode hash --out clean.jsonl
python3 skills/guardrails-and-safety/scripts/injection_scan.py knowledge-base/
python3 skills/cost-latency-estimator/scripts/estimate_cost.py config.json --compare
python3 skills/conversation-log-analysis/scripts/analyze_logs.py logs.jsonl --intents intents.json
python3 skills/agent-deployment-checklist/scripts/readiness_check.py launch-checklist.md --require-evidence
```

They fit together as a lifecycle:

```
agent-scoping -> tool-schema-design + system-prompt-review + rag-ingestion
             -> eval-harness + guardrails-and-safety + cost-latency-estimator
             -> agent-deployment-checklist -> conversation-log-analysis -> (new eval cases)
```

## How skills work

At startup the agent loads only each skill's `name` and `description` (about 100 tokens
each). When your request matches a description, it reads that skill's `SKILL.md`: the
workflow, decision points and rules. Longer material lives in `references/` and templates in
`assets/`; they are read only when a step needs them. Scripts run as normal commands, so their
output is exact and repeatable.

```
skills/<skill-name>/
  SKILL.md          frontmatter (name, description) + workflow
  scripts/          standalone Python 3 helpers (stdlib only, --help, --json)
  references/       checklists, guides, patterns
  assets/           templates and example inputs (spec, checklist, config, eval cases)
```

## FAQ

**Do I need a particular LLM provider or framework?**
No. Nothing here calls a model. The skills work with any LLM provider, self-hosted model or agent
framework; the scripts read files you export (tool definitions, prompts, docs, recorded outputs,
logs). The test suite checks that skill content stays free of vendor names.

**Where do the prices in the cost estimator come from?**
From you. `assets/example-config.json` contains clearly marked placeholder numbers. Copy it and
enter your LLM provider's current published prices and your measured speeds.

**How does the eval harness run the model?**
It does not. Record outputs with your own runner (the same code path as production) and score
them. Rubric items that need judgement are exported for human or judge-model grading and merged
back with `--grades`.

**Is the injection scanner enough to stop prompt injection?**
No. It is a tripwire for obvious patterns in content you index or read. Real protection comes from
limiting what tools can do, enforcing confirmation in code and treating retrieved content as data.
See `guardrails-and-safety`.

**Does anything leave my machine?**
No. No script makes network calls or sends telemetry.

**Languages other than English?**
Placeholder, refusal and failure-phrase heuristics are English. Intent rules, extra PII patterns
(`--pattern`) and label fields let you adapt them; better multilingual support is on the roadmap.

## Roadmap

Ideas for new skills and features (great first contributions; see [CONTRIBUTING.md](CONTRIBUTING.md)):

- `intent-taxonomy-builder` - cluster sampled user messages into an intent list with examples
- `knowledge-gap-finder` - match failed questions from logs against the knowledge base
- `handover-message-design` - templates and checks for human handover summaries
- `agent-memory-design` - what to remember across sessions, retention and deletion rules
- `voice-agent-checklist` - latency budgets, barge-in, spelling of names and numbers
- `retrieval-eval` - hit@k and MRR from question/expected-source pairs
- `prompt-diff-review` - compare two prompt versions rule by rule
- Multilingual phrase lists for `conversation-log-analysis` and `system-prompt-review`

## Contributing

Contributions are welcome: new checks, new skills, fixes and better docs. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for the skill template, the quality bar and
how to run the validator and tests:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py && ruff check . && ruff format --check . && pytest
```

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and report security issues
privately as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) (c) Saizul Amin
