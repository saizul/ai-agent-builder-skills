## What does this pull request do?

<!-- One or two sentences. Link the issue: "Closes #123". -->

## Type

- [ ] New skill
- [ ] New check or option in an existing script
- [ ] Workflow / reference improvement
- [ ] Bug fix
- [ ] Repository tooling (validator, CI)

## Checklist

- [ ] `python tools/validate_skills.py` passes
- [ ] `ruff check . && ruff format --check .` passes
- [ ] `pytest` passes; new script behaviour has tests with fixtures in `tests/fixtures/<skill>/`
- [ ] Scripts use only the Python standard library (or POSIX shell), support `--help`, have a
      `--json` option where output is structured, and exit non-zero on findings
- [ ] Read-only by default, no network calls, never prints secrets or personal data
- [ ] Vendor-neutral: no LLM provider, model or framework names in skill content (say "LLM provider")
- [ ] No real customer data, secrets or API keys in fixtures (use example.com, documentation IP
      ranges such as 203.0.113.0/24 and obviously fake values)
- [ ] New skills: listed in `.claude-plugin/marketplace.json`, the README skills table, AGENTS.md and CHANGELOG.md
