import json

from conftest import SKILLS, load_script, run_script

SKILL = "agent-scoping"
SCRIPT = "spec_lint.py"
m = load_script(SKILL, SCRIPT)


def codes(rep, severity=None):
    return [(f["section"], f["message"]) for f in rep["findings"] if severity in (None, f["severity"])]


def test_good_spec_is_ready(fixtures):
    rep = m.lint((fixtures / SKILL / "good-spec.md").read_text())
    assert rep["ready"] is True
    assert rep["findings"] == []
    assert rep["sections_missing"] == []


def test_bad_spec_blockers(fixtures):
    rep = m.lint((fixtures / SKILL / "bad-spec.md").read_text())
    blockers = codes(rep, "blocker")
    assert ("out_of_scope", "section is missing") in blockers
    assert ("handover", "section is missing") in blockers
    assert any("issue_refund" in msg and "confirm" in msg for _, msg in blockers)
    majors = [msg for _, msg in codes(rep, "major")]
    assert any("search_kb" in msg and "access level" in msg for msg in majors)
    assert any("numeric target" in msg for msg in majors)
    assert rep["ready"] is False


def test_template_is_not_ready():
    rep = m.lint((SKILLS / SKILL / "assets" / "agent-spec-template.md").read_text())
    assert rep["ready"] is False
    # The template has every section, only placeholders are missing.
    assert rep["sections_missing"] == []


def test_write_tool_with_confirmation_passes():
    spec = """## Tools
| Tool | Purpose | Access | Confirmation required |
| --- | --- | --- | --- |
| create_return | open a return | write | yes, after summary |
"""
    rep = m.lint(spec)
    assert not any("create_return" in f["message"] for f in rep["findings"])


def test_kpi_measurement_missing():
    spec = """## KPIs
| KPI | Baseline | Target | How measured |
| --- | --- | --- | --- |
| Containment | 0% | 40% | |
"""
    rep = m.lint(spec)
    assert any("no measurement method" in f["message"] for f in rep["findings"])
    assert not any("numeric target" in f["message"] for f in rep["findings"])


def test_cli_exit_codes(fixtures, tmp_path):
    assert run_script(SKILL, SCRIPT, str(fixtures / SKILL / "good-spec.md")).returncode == 0
    r = run_script(SKILL, SCRIPT, str(fixtures / SKILL / "bad-spec.md"), "--json")
    assert r.returncode == 1
    assert json.loads(r.stdout)["ready"] is False
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.md")).returncode == 2


def test_allow_major_only_blockers_fail(tmp_path, fixtures):
    text = (fixtures / SKILL / "good-spec.md").read_text().replace("| 40% by week 8 |", "| much higher |")
    spec = tmp_path / "spec.md"
    spec.write_text(text)
    assert run_script(SKILL, SCRIPT, str(spec)).returncode == 1
    assert run_script(SKILL, SCRIPT, str(spec), "--allow-major").returncode == 0
