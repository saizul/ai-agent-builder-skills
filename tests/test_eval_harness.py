import json

from conftest import SKILLS, load_script, run_script

SKILL = "eval-harness"
SCRIPT = "run_evals.py"
m = load_script(SKILL, SCRIPT)


def check(ctype, output, tool_calls=None, **kw):
    status, _ = m.run_check(
        {"type": ctype, **kw}, {"output": output, "tool_calls": tool_calls or []}, {}, "x"
    )
    return status


def test_text_checks():
    assert check("exact", " yes ", value="yes") == "pass"
    assert check("exact", "Yes", value="yes") == "fail"
    assert check("exact", "Yes", value="yes", ignore_case=True) == "pass"
    assert check("contains", "Refund in 14 DAYS", value="14 days") == "pass"
    assert check("contains", "a b", values=["a", "c"]) == "fail"
    assert check("contains", "a b", values=["a", "c"], all=False) == "pass"
    assert check("contains", "ABC", value="abc", ignore_case=False) == "fail"
    assert check("not_contains", "we guarantee it", value="Guarantee") == "fail"
    assert check("one_of", "No", values=["yes", "no"]) == "pass"
    assert check("regex", "order #123", pattern=r"#\d+") == "pass"
    assert check("regex", "**bold**", pattern=r"\*\*", negate=True) == "fail"
    assert check("max_chars", "x" * 10, value=5) == "fail"
    assert check("min_chars", "x" * 10, value=5) == "pass"


def test_json_and_tool_checks():
    assert check("json_field", '{"a": {"b": [1, 2]}}', path="a.b.1", value=2) == "pass"
    assert check("json_field", '{"a": 1}', path="a.b") == "fail"
    assert check("json_field", "not json", path="a") == "fail"
    assert check("tool_called", "", tool_calls=[{"name": "lookup"}], value="lookup") == "pass"
    assert check("tool_not_called", "", tool_calls=["lookup"], value="lookup") == "fail"


def test_rubric_with_grades():
    chk = {"type": "rubric", "criteria": [{"id": "k", "keywords": ["sorry"]}, {"id": "tone"}]}
    rec = {"output": "Sorry about that"}
    assert m.run_check(chk, rec, {}, "c1")[0] == "needs_review"
    assert m.run_check(chk, rec, {("c1", "tone"): True}, "c1")[0] == "pass"
    assert m.run_check(chk, rec, {("c1", "tone"): False}, "c1")[0] == "fail"
    assert m.run_check(chk, {"output": "no"}, {("c1", "tone"): True}, "c1")[0] == "fail"


def test_unknown_check_type():
    try:
        m.run_check({"type": "magic"}, {"output": ""}, {}, "x")
    except ValueError as exc:
        assert "magic" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_evaluate_fixture(fixtures):
    d = fixtures / SKILL
    cases, outputs = m.read_jsonl(d / "cases.jsonl"), m.read_jsonl(d / "outputs.jsonl")
    rep = m.evaluate(cases, outputs)
    status = {r["id"]: r["status"] for r in rep["results"]}
    assert status == {
        "status-1": "pass",
        "status-no-number": "pass",
        "refund-limit": "needs_review",
        "out-of-scope-legal": "fail",
        "router-json": "pass",
    }
    assert rep["unknown_outputs"] == ["extra-output"]
    assert rep["pass_rate"] == 0.6
    assert rep["pass_rate_scored"] == 0.75
    assert rep["by_tag"]["order-status"]["pass_rate"] == 1.0
    graded = m.evaluate(cases, outputs, m.read_jsonl(d / "grades.jsonl"))
    assert graded["counts"]["pass"] == 4


def test_missing_output():
    rep = m.evaluate([{"id": "a", "checks": [{"type": "contains", "value": "x"}]}], [])
    assert rep["results"][0]["status"] == "missing_output"


def test_example_cases_asset_is_valid():
    cases = m.read_jsonl(SKILLS / SKILL / "assets" / "example-cases.jsonl")
    assert len(cases) >= 5
    outputs = [{"id": c["id"], "output": ""} for c in cases]
    m.evaluate(cases, outputs)  # every check type in the asset is known


def test_cli_review_grades_baseline(fixtures, tmp_path):
    d = fixtures / SKILL
    review = tmp_path / "review.jsonl"
    r = run_script(
        SKILL, SCRIPT, str(d / "cases.jsonl"), str(d / "outputs.jsonl"), "--review-out", str(review)
    )
    assert r.returncode == 0
    rows = [json.loads(x) for x in review.read_text().splitlines()]
    assert [(x["id"], x["criterion"]) for x in rows] == [("refund-limit", "polite-and-clear")]
    assert rows[0]["pass"] is None and rows[0]["output"]

    base = tmp_path / "base.json"
    r = run_script(
        SKILL,
        SCRIPT,
        str(d / "cases.jsonl"),
        str(d / "outputs.jsonl"),
        "--grades",
        str(d / "grades.jsonl"),
        "--json",
    )
    base.write_text(r.stdout)
    assert json.loads(r.stdout)["pass_rate"] == 0.8

    r = run_script(
        SKILL,
        SCRIPT,
        str(d / "cases.jsonl"),
        str(d / "outputs-v2.jsonl"),
        "--grades",
        str(d / "grades.jsonl"),
        "--baseline",
        str(base),
        "--fail-on-regression",
    )
    assert r.returncode == 1
    assert "regressions: status-1" in r.stdout
    assert "fixed: out-of-scope-legal" in r.stdout

    r = run_script(SKILL, SCRIPT, str(d / "cases.jsonl"), str(d / "outputs.jsonl"), "--min-pass-rate", "0.9")
    assert r.returncode == 1
    r = run_script(
        SKILL,
        SCRIPT,
        str(d / "cases.jsonl"),
        str(d / "outputs.jsonl"),
        "--tag",
        "routing",
        "--min-pass-rate",
        "1",
    )
    assert r.returncode == 0
    assert "1 case(s)" in r.stdout


def test_cli_bad_input(tmp_path, fixtures):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "a"}\n{oops\n')
    r = run_script(SKILL, SCRIPT, str(bad), str(fixtures / SKILL / "outputs.jsonl"))
    assert r.returncode == 2
    assert "bad.jsonl:2" in r.stderr
    dup = tmp_path / "dup.jsonl"
    dup.write_text('{"id": "a"}\n{"id": "a"}\n')
    assert run_script(SKILL, SCRIPT, str(dup), str(fixtures / SKILL / "outputs.jsonl")).returncode == 2
