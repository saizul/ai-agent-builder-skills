import json

from conftest import SKILLS, load_script, run_script

SKILL = "system-prompt-review"
SCRIPT = "prompt_review.py"
m = load_script(SKILL, SCRIPT)


def codes(text, **kw):
    return {f["code"] for f in m.review(text, **kw)["findings"]}


def test_good_prompt_clean(fixtures):
    rep = m.review((fixtures / SKILL / "good-prompt.txt").read_text())
    assert rep["findings"] == []
    assert rep["stats"]["estimated_tokens"] > 100


def test_bad_prompt(fixtures):
    found = codes((fixtures / SKILL / "bad-prompt.txt").read_text())
    for code in (
        "contradiction",
        "no-refusal-rule",
        "no-handover-rule",
        "placeholder",
        "secret",
        "no-tool-rules",
        "hardcoded-date",
        "duplicate",
        "vague",
        "shouting",
        "no-format",
    ):
        assert code in found, code


def test_secret_value_is_not_echoed(fixtures):
    rep = m.review((fixtures / SKILL / "bad-prompt.txt").read_text())
    secret = [f for f in rep["findings"] if f["code"] == "secret"][0]
    assert "example-only" not in secret["evidence"]
    assert "line 7" in secret["evidence"]


def test_length_thresholds():
    base = "You help with orders. Do not answer unrelated questions. Hand over to a human agent when asked. Answer in two sentences. "
    assert "long" in codes(base * 60, max_tokens=1000)
    assert "too-long" in codes(base * 200, max_tokens=1000)
    assert not codes(base, max_tokens=1000)


def test_tools_flag():
    text = "Only answer questions about orders. Hand over to a human agent if asked. Keep answers brief."
    assert "no-tool-rules" in codes(text, has_tools=True)
    assert "no-tool-rules" not in codes(text, has_tools=False)
    ok = text + " Call lookup_order when the user gives an order number."
    assert "no-tool-rules" not in codes(ok, has_tools=True)


def test_skeleton_reference_has_placeholders():
    rep = m.review((SKILLS / SKILL / "references" / "prompt-skeleton.md").read_text())
    assert "placeholder" in {f["code"] for f in rep["findings"]}


def test_cli(fixtures):
    r = run_script(SKILL, SCRIPT, str(fixtures / SKILL / "bad-prompt.txt"), "--json")
    assert r.returncode == 1
    assert json.loads(r.stdout)["stats"]["words"] > 50
    assert run_script(SKILL, SCRIPT, str(fixtures / SKILL / "good-prompt.txt")).returncode == 0
    r = run_script(SKILL, SCRIPT, "-", "--fail-on", "low", stdin="Answer questions. Be helpful as needed.")
    assert r.returncode == 1
    assert run_script(SKILL, SCRIPT, "/nonexistent/prompt.txt").returncode == 2
