import json

from conftest import load_script, run_script

SKILL = "conversation-log-analysis"
SCRIPT = "analyze_logs.py"
m = load_script(SKILL, SCRIPT)


def report(fixtures, rules=True):
    d = fixtures / SKILL
    convs = m.load([d / "messages.jsonl", d / "conversations.jsonl"])
    intents = json.loads((d / "intents.json").read_text()) if rules else {}
    return m.analyse(convs, intents, examples=10)


def test_counts_and_rates(fixtures):
    rep = report(fixtures)
    assert rep["conversations"] == 5
    assert rep["user_turns"] == 8
    assert rep["handover_rate"] == 0.4  # c2 (event) and c11 (flag + human role)
    assert rep["failure_conversation_rate"] == 0.4  # c2, c3
    assert rep["abandon_rate"] == 0.2  # c3 ends with the user
    assert rep["tool_errors"] == 1
    assert rep["failure_reasons"] == {
        "assistant_could_not_help": 2,
        "user_frustrated_or_asked_for_human": 2,
        "user_repeated": 1,
        "tool_error": 1,
    }


def test_intents(fixtures):
    intents = {i["intent"]: i for i in report(fixtures)["intents"]}
    assert intents["order_status"]["conversations"] == 2  # rule match + label
    assert intents["returns"]["handover_rate"] == 1.0
    assert intents["refunds"]["abandoned"] == 1
    assert intents["unclassified"]["conversations"] == 1
    no_rules = {i["intent"] for i in report(fixtures, rules=False)["intents"]}
    assert no_rules == {"order_status", "unclassified"}


def test_examples_are_masked(fixtures):
    rep = report(fixtures)
    texts = " ".join(e["text"] for e in rep["failure_examples"])
    assert "kim@example.com" not in texts
    assert m.clean("call +44 20 7946 0958 or a@b.co") == "call [PHONE] or [EMAIL]"
    assert m.clean("x" * 200, 20).endswith("...")


def test_content_parts_and_roles():
    assert m.content_of({"content": [{"text": "a"}, {"text": "b"}]}) == "a b"
    assert m.role_of({"role": "Bot"}) == "assistant"
    assert m.role_of({"sender": "operator"}) == "human"


def test_cli(fixtures, tmp_path):
    d = fixtures / SKILL
    res = run_script(
        SKILL,
        SCRIPT,
        str(d / "messages.jsonl"),
        str(d / "conversations.jsonl"),
        "--intents",
        str(d / "intents.json"),
    )
    assert res.returncode == 0
    assert "handover rate 40.0%" in res.stdout
    res = run_script(SKILL, SCRIPT, str(d / "messages.jsonl"), "--json", "--max-handover-rate", "0.2")
    assert res.returncode == 1
    assert json.loads(res.stdout)["conversations"] == 3
    assert run_script(SKILL, SCRIPT, str(d / "messages.jsonl"), "--max-failure-rate", "0.9").returncode == 0
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{nope\n")
    assert run_script(SKILL, SCRIPT, str(bad)).returncode == 2
