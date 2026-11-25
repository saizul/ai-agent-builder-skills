import json

import pytest

from conftest import SKILLS, load_script, run_script

SKILL = "cost-latency-estimator"
SCRIPT = "estimate_cost.py"
m = load_script(SKILL, SCRIPT)


def cfg(fixtures, *sets):
    c = m.load_config(fixtures / SKILL / "simple-config.json", list(sets))
    assert m.validate(c) == []
    return c


def test_hand_computed_estimate(fixtures):
    # turn 1 input 1100, turn 2 input 1300 (history 200); output 2 x 100.
    res = m.estimate(cfg(fixtures))
    model = res["by_model"]["m"]
    assert model["tokens_per_conversation"] == {"input": 2400, "cached_input": 0, "output": 200}
    assert model["cost_per_conversation"] == pytest.approx(0.0032)
    assert res["conversations_per_month"] == 3000
    assert res["llm_cost_per_month"] == pytest.approx(9.6)
    assert res["total_cost_per_month"] == pytest.approx(19.6)
    assert res["over_budget"] is False
    assert model["latency_ms"]["avg_turn"] == 1500  # 500 ttft + 100 tokens at 100/s


def test_caching_history_and_tools(fixtures):
    cached = m.estimate(cfg(fixtures, "caching.cached_fraction_of_static=0.5"))["by_model"]["m"]
    assert cached["tokens_per_conversation"]["cached_input"] == 1000
    assert cached["cost_per_conversation"] == pytest.approx(0.0023)
    no_hist = m.estimate(cfg(fixtures, "tokens.history_carryover=false"))["by_model"]["m"]
    assert no_hist["tokens_per_conversation"]["input"] == 2200
    tools = m.estimate(
        cfg(fixtures, "tokens.tool_calls_per_turn=1", "tokens.tool_result=200", "latency.tool_latency_ms=300")
    )
    t = tools["by_model"]["m"]
    assert t["model_calls_per_conversation"] == 4
    # (1100*2 + 200) + (1300*2 + 200)
    assert t["tokens_per_conversation"]["input"] == 5200
    assert t["latency_ms"]["avg_turn"] == 2 * 500 + 1000 + 300


def test_routing_mix(fixtures):
    c = cfg(fixtures)
    c["models"]["big"] = {"input_per_mtok": 10.0, "output_per_mtok": 40.0}
    c["routing"] = {"m": 0.5, "big": 0.5}
    assert m.validate(c) == []
    res = m.estimate(c)
    assert res["by_model"]["big"]["cost_per_conversation"] == pytest.approx(0.032)
    assert res["llm_cost_per_month"] == pytest.approx(1500 * 0.0032 + 1500 * 0.032)
    assert res["over_budget"] is True


def test_validation_errors(fixtures):
    c = cfg(fixtures)
    c["routing"] = {"m": 0.7}
    assert any("add up to 1.0" in e for e in m.validate(c))
    c["routing"] = {"ghost": 1.0}
    assert any("unknown model" in e for e in m.validate(c))
    assert m.validate(m.load_config(None, [])) == [
        "config needs a 'models' table with your LLM provider's prices"
    ]
    c = cfg(fixtures)
    c["models"]["m"]["input_per_mtok"] = -1
    assert any("non-negative" in e for e in m.validate(c))


def test_example_config_runs():
    res = run_script(
        SKILL, SCRIPT, str(SKILLS / SKILL / "assets" / "example-config.json"), "--json", "--compare"
    )
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert [s["multiplier"] for s in data["traffic_scenarios"]] == [0.5, 1, 2, 5]
    assert data["total_cost_per_month"] > data["llm_cost_per_month"]


def test_cli_budget_and_overrides(fixtures):
    path = str(fixtures / SKILL / "simple-config.json")
    assert run_script(SKILL, SCRIPT, path).returncode == 0
    res = run_script(SKILL, SCRIPT, path, "--set", "traffic.conversations_per_day=1000")
    assert res.returncode == 1
    assert "OVER budget" in res.stdout
    assert run_script(SKILL, SCRIPT, path, "--set", 'routing={"x": 1}').returncode == 2
    assert run_script(SKILL, SCRIPT, path, "--set", "nonsense").returncode == 2


def test_tokens_file(tmp_path):
    f = tmp_path / "prompt.txt"
    f.write_text("x" * 400)
    res = run_script(SKILL, SCRIPT, "--tokens-file", str(f), "--json")
    assert res.returncode == 0
    assert json.loads(res.stdout)[0]["estimated_tokens"] == 100


def test_no_vendor_prices_in_script():
    src = (SKILLS / SKILL / "scripts" / SCRIPT).read_text()
    assert '_per_mtok": 0.' not in src and 'per_mtok": 1' not in src
