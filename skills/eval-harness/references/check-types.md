# Check types

All text checks look at `output` (string). Case-insensitive unless noted.

| type | fields | passes when |
| --- | --- | --- |
| `exact` | `value`, `ignore_case` (default false) | output (trimmed) equals value |
| `contains` | `value` or `values`, `all` (default true) | all (or any, with `"all": false`) values appear |
| `not_contains` | `value` or `values` | none of the values appear |
| `one_of` | `values` | output (trimmed) equals one of the values (classification) |
| `regex` | `pattern`, `ignore_case`, `negate` | pattern found (or not found with `negate`) |
| `max_chars` / `min_chars` | `value` | output length within the limit |
| `json_field` | `path` (dot path, list indexes allowed), optional `value` | output parses as JSON and field exists / equals value |
| `tool_called` / `tool_not_called` | `value` (tool name) | name in / not in `tool_calls` (strings or `{"name": ...}`) |
| `rubric` | `criteria`: list of `{id, keywords?, description?}` | every criterion passes |

Set `"ignore_case": false` on `contains`/`not_contains`/`one_of` for case-sensitive matching.

Rubric criteria:
- with `keywords`: pass if any keyword appears (automatic, cheap, crude)
- without `keywords`: `needs_review` until a grade arrives via `--grades` (JSONL:
  `{"id": "case-id", "criterion": "criterion-id", "pass": true}`)

A case passes only if every check passes. A case with any `needs_review` check (and no
failing check) is reported as `needs_review` and does not count as a pass.

## Results JSON

`--json` prints `total`, `counts`, `pass_rate`, `pass_rate_scored`, `by_tag`, `results` (per case:
status and per-check detail), `unknown_outputs`, and with `--baseline`: `regressions`, `fixed`.
Save it per release and pass it as `--baseline` next time.

## Exit codes

0 ok; 1 pass rate below `--min-pass-rate` or regressions with `--fail-on-regression`; 2 bad input.
