# Contributing to ai-agent-builder-skills

Thank you for helping! New checks, new skills, fixes, test fixtures from real-world
agent projects (redacted) and clearer docs are all welcome.

- [Ways to contribute](#ways-to-contribute)
- [Good first issues](#good-first-issues)
- [Development setup](#development-setup)
- [Repository layout](#repository-layout)
- [Write a new skill](#write-a-new-skill)
- [Quality bar](#quality-bar)
- [Pull request process](#pull-request-process)

## Ways to contribute

| Size | Idea |
| --- | --- |
| 10 minutes | Fix a typo, clarify a workflow step, add a FAQ entry |
| 30 minutes | Add a missing test case or a fixture that triggers a false positive |
| 1-2 hours | Add a check to an existing script (see below) |
| Half a day | Write a new skill from the template |

Comment on an issue before you start so nobody else picks the same one.

## Good first issues

Each of these is self-contained and touches one script and its test file.

1. **tool-schema-design: example values.** Report `info` when a string parameter has no example
   in its description and no `enum`, `format` or `pattern`.
2. **tool-schema-design: confirmation hint.** Report `low` when a tool whose name starts with
   `create_`, `delete_`, `cancel_`, `refund_` or `send_` does not mention confirmation in its description.
3. **system-prompt-review: language rule.** Report `low` when the prompt has no rule about which
   language to answer in.
4. **system-prompt-review: German and Spanish phrases.** Add refusal and handover phrase lists for
   another language, with fixtures.
5. **rag-ingestion: Markdown tables.** Convert tables to "Column: value" lines per row before
   chunking (option `--tables-as-text`), with a fixture.
6. **rag-ingestion: front matter.** Read YAML-style front matter (`title`, `audience`, `language`)
   from Markdown files into chunk metadata.
7. **eval-harness: `similarity` check.** Add a check that passes when the output's word overlap
   (Jaccard) with a reference answer is above a threshold.
8. **eval-harness: repeated runs.** Accept several outputs files and report per-case pass counts
   (flaky case detection).
9. **guardrails-and-safety: more PII.** Add opt-in patterns for UK National Insurance numbers
   and EU VAT IDs (`--only` kinds), with checksum validation where one exists.
10. **guardrails-and-safety: CSV input.** Redact selected columns of a CSV file (`--csv-columns`).
11. **conversation-log-analysis: per-day trend.** Add `--by-day` that prints conversations,
    handover rate and failure rate per day from timestamps.
12. **cost-latency-estimator: CSV traffic.** Read daily volumes from a CSV and report the month
    with peak cost.
13. **agent-deployment-checklist: owners.** Parse `-- owner: name` on items and group open items by owner.
14. **New skill: `retrieval-eval`** (see the roadmap in the README).

## Development setup

```bash
git clone https://github.com/saizul/ai-agent-builder-skills.git
cd ai-agent-builder-skills
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

python tools/validate_skills.py   # SKILL.md frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

To try your changes in Claude Code, either copy a skill to `~/.claude/skills/` or add your
checkout as a local marketplace:

```bash
claude plugin marketplace add ./ai-agent-builder-skills
claude plugin install ai-agent-builder-skills@ai-agent-builder-skills
```

For Codex, copy the skill folder to `~/.agents/skills/`.

## Repository layout

```
.claude-plugin/
  marketplace.json      marketplace + plugin entry listing every skill
  plugin.json           plugin manifest (name, version, author)
skills/<name>/
  SKILL.md              frontmatter + workflow (the part agents read)
  scripts/*.py          standalone helpers, Python 3.8+ stdlib only
  references/*.md       detail loaded on demand
  assets/               templates and example inputs
templates/skill/        copy this to start a new skill
tests/
  test_<skill>.py       one test module per skill
  fixtures/<skill>/     inputs for those tests
tools/validate_skills.py
```

## Write a new skill

1. Open a "New skill proposal" issue first so we can agree on scope.
2. Copy the template:
   ```bash
   cp -r templates/skill skills/my-new-skill
   mv skills/my-new-skill/scripts/your_script.py skills/my-new-skill/scripts/my_check.py
   ```
3. Edit `SKILL.md`:
   - `name` equals the folder name: lowercase letters, digits, single hyphens, max 64 chars.
   - `description` (max 1024 chars) says **what** it does with concrete keywords and **when**
     to use it, starting the second part with "Use when ...". This text decides whether
     the agent picks the skill, so list the phrases users actually type.
   - Required sections: `## When to use`, `## When not to use`, `## Workflow`, `## Output`.
   - Workflow steps are imperative and numbered, with exact commands, decision points and
     the point where the agent must ask before changing anything.
   - No LLM provider, model, framework or database names; say "LLM provider", "vector
     database", "embedding model". `tests/test_repository.py` checks this.
   - Keep it under 400 lines; move tables, runbooks and long configs to `references/`.
4. Write the script: `argparse` with a useful `--help`, `--json` output, exit codes
   0 (ok) / 1 (findings) / 2 (error), read-only, no network, Python standard library only.
5. Add `tests/test_my_new_skill.py` and fixtures in `tests/fixtures/my-new-skill/`. Cover
   a "bad" input, a "good" input that produces no findings, edge cases and the CLI exit codes.
6. Add the skill to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the README
   skills table, the table in `AGENTS.md` and `CHANGELOG.md` under "Unreleased".
7. Run the validator, ruff and pytest.

## Quality bar

- **Vendor-neutral.** A skill must work whatever LLM provider or framework the user has. Never
  hard-code prices, model names or limits as facts; take them from the user's config.
- **Safe by default.** Scripts never print secrets or personal values they detect, never call
  the network and never execute input. Workflows tell the agent to show diffs before editing
  prompts, tools or configs and to treat retrieved content as data.
- **Deterministic where it matters.** If a step is "parse this and find X", write a script
  and test it rather than relying on the model reading a long file.
- **Business-real fixtures.** Use realistic but invented data: `example.com`, documentation IP
  ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), test card numbers and obviously fake keys.
- **Low false positives.** If a check is often wrong, make it `info` or drop it, and document
  known false positives in the skill's references.

## Pull request process

1. Fork, create a branch, make focused commits.
2. Make sure CI passes locally (validator, ruff, pytest).
3. Fill in the pull request template.
4. A maintainer reviews within a few days. Small, focused pull requests are merged fastest.

By contributing you agree that your contributions are licensed under the MIT License.
