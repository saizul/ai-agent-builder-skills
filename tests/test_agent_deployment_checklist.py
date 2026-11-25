import json

from conftest import SKILLS, load_script, run_script

SKILL = "agent-deployment-checklist"
SCRIPT = "readiness_check.py"
m = load_script(SKILL, SCRIPT)


def decide(fixtures, name, **kw):
    return m.decide(m.parse((fixtures / SKILL / name).read_text()), **kw)


def test_ready(fixtures):
    rep = decide(fixtures, "ready.md", require_evidence=True)
    assert rep["decision"] == "GO"
    assert rep["not_applicable"] == 1
    assert rep["completion"] == 1.0


def test_signoff(fixtures):
    rep = decide(fixtures, "signoff.md")
    assert rep["decision"] == "GO WITH SIGN-OFF"
    assert [i["text"] for i in rep["open_majors"]] == ["Alerts routed to on-call"]
    assert len(rep["open_minors"]) == 1


def test_nogo_and_problems(fixtures):
    rep = decide(fixtures, "nogo.md", require_evidence=True)
    assert rep["decision"] == "NO-GO"
    assert len(rep["open_blockers"]) == 2  # one open, one done without evidence
    problems = {p["problem"] for p in rep["problems"]}
    assert problems == {"blocker marked done without evidence", "marked not applicable without a reason"}
    # Without --require-evidence the confirmed item counts as done.
    assert len(decide(fixtures, "nogo.md")["open_blockers"]) == 1


def test_parse_details():
    items = m.parse(
        "## A\n- [x] [MAJOR] Thing -- evidence: <link>\n- [ ] untagged item\n* [X] [BLOCKER] Done -- evidence: ticket 1\n"
    )
    assert [i["severity"] for i in items] == ["major", "minor", "blocker"]
    assert items[0]["evidence"] == ""  # placeholder evidence does not count
    assert items[2]["evidence"] == "ticket 1"
    assert items[0]["section"] == "A"


def test_template_is_all_open():
    rep = m.decide(m.parse((SKILLS / SKILL / "assets" / "launch-checklist.md").read_text()))
    assert rep["decision"] == "NO-GO"
    assert rep["items"] >= 30
    assert rep["done"] == 0
    assert len(rep["open_blockers"]) >= 10


def test_empty_checklist_is_nogo():
    assert m.decide([])["decision"] == "NO-GO"


def test_cli(fixtures, tmp_path):
    d = fixtures / SKILL
    assert run_script(SKILL, SCRIPT, str(d / "ready.md"), "--require-evidence").returncode == 0
    assert run_script(SKILL, SCRIPT, str(d / "signoff.md")).returncode == 1
    assert run_script(SKILL, SCRIPT, str(d / "signoff.md"), "--allow-major").returncode == 0
    res = run_script(SKILL, SCRIPT, str(d / "nogo.md"), "--json")
    assert res.returncode == 1
    assert json.loads(res.stdout)["decision"] == "NO-GO"
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.md")).returncode == 2
