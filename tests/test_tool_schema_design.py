import json

from conftest import load_script, run_script

SKILL = "tool-schema-design"
SCRIPT = "tool_schema_lint.py"
m = load_script(SKILL, SCRIPT)


def lint_file(fixtures, name):
    doc = json.loads((fixtures / SKILL / name).read_text())
    return m.lint_tools(m.extract_tools(doc))


def by_code(findings):
    out = {}
    for f in findings:
        out.setdefault(f["code"], []).append(f)
    return out


def test_good_tools_clean(fixtures):
    assert lint_file(fixtures, "good-tools.json") == []


def test_wrapped_and_input_schema_shapes(fixtures):
    findings = lint_file(fixtures, "wrapped-tools.json")
    assert findings == []
    tools = m.extract_tools(json.loads((fixtures / SKILL / "wrapped-tools.json").read_text()))
    assert [t["name"] for t in tools] == ["get_weather_forecast", "list_invoices"]


def test_bad_tools_findings(fixtures):
    codes = by_code(lint_file(fixtures, "bad-tools.json"))
    for code in (
        "missing-description",
        "vague-name",
        "ambiguous-name",
        "missing-param-description",
        "unknown-required",
        "enum-candidate",
        "range-in-prose",
        "negative-boolean",
        "array-without-items",
        "missing-type",
        "duplicate-name",
        "root-not-object",
        "invalid-name",
        "missing-schema",
        "overlapping-tools",
    ):
        assert code in codes, code
    assert codes["unknown-required"][0]["message"].startswith("'required' lists 'order_id'")
    assert codes["enum-candidate"][0]["path"] == "status"


def test_nested_object_and_array_items():
    tool = {
        "name": "create_ticket",
        "description": "Create a support ticket. Use when the user reports a problem the agent cannot solve.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["customer"],
            "properties": {
                "customer": {"type": "object", "description": "Customer details for the ticket"},
                "items": {
                    "type": "array",
                    "description": "Order lines concerned",
                    "items": {"type": "string"},
                },
            },
        },
    }
    codes = by_code(m.lint_tools([tool]))
    assert "open-object" in codes
    assert codes["missing-param-description"][0]["path"] == "items[]"
    assert codes["missing-param-description"][0]["severity"] == "low"


def test_too_many_params():
    props = {f"field_{i}": {"type": "string", "description": "A described field value"} for i in range(14)}
    tool = {
        "name": "update_profile",
        "description": "Update profile fields. Use when the user asks to change their profile details.",
        "parameters": {"type": "object", "properties": props, "required": [], "additionalProperties": False},
    }
    assert "too-many-params" in by_code(m.lint_tools([tool]))


def test_cli(fixtures):
    r = run_script(SKILL, SCRIPT, str(fixtures / SKILL / "bad-tools.json"), "--json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["tools"] == 4
    assert data["counts"]["high"] >= 4
    r = run_script(SKILL, SCRIPT, str(fixtures / SKILL / "good-tools.json"))
    assert r.returncode == 0
    assert "0 finding(s)" in r.stdout
    # Only info findings: does not fail at the default level.
    r = run_script(
        SKILL,
        SCRIPT,
        "-",
        stdin=json.dumps(
            {
                "name": "list_invoices",
                "description": "List invoices for the signed-in customer. Use when asked for billing history.",
                "parameters": {
                    "type": "object",
                    "properties": {"year": {"type": "integer", "description": "Invoice year, e.g. 2026"}},
                    "required": [],
                },
            }
        ),
    )
    assert r.returncode == 0, r.stdout
    assert "additional-properties" in r.stdout


def test_cli_errors(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert run_script(SKILL, SCRIPT, str(bad)).returncode == 2
    assert run_script(SKILL, SCRIPT, str(tmp_path / "nope.json")).returncode == 2
