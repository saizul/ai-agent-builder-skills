#!/usr/bin/env python3
"""Lint JSON Schema tool (function) definitions before an LLM agent uses them.

Accepts a JSON file holding one tool, a list of tools, or an object with a
"tools" or "functions" list. Each tool may be flat
({"name", "description", "parameters" | "input_schema" | "inputSchema"}) or
wrapped ({"type": "function", "function": {...}}).

Checks: tool names, missing/short descriptions, parameters without type or
description, ambiguous parameter names, enum-like strings without "enum",
"required" entries that do not exist, missing "required", open objects,
array items without a schema, too many parameters, negative booleans,
duplicate names and tools whose descriptions overlap heavily.

Exit codes: 0 = no findings at or above --fail-on, 1 = findings, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
AMBIGUOUS_PARAMS = {
    "data",
    "info",
    "value",
    "input",
    "obj",
    "object",
    "payload",
    "params",
    "args",
    "item",
    "thing",
    "stuff",
    "text",
    "string",
    "query2",
    "x",
    "y",
    "val",
    "param",
    "arg",
}
ENUM_HINT_RE = re.compile(
    r"(\bone of\b|\beither\b|\ballowed values?\b|\bmust be (?:'|\")|\bpossible values?\b|"
    r"(?:'[a-z0-9_-]+'|\"[a-z0-9_-]+\"|`[a-z0-9_-]+`)\s*(?:,|/|\|| or )\s*(?:'|\"|`))",
    re.I,
)
NEGATIVE_BOOL_RE = re.compile(r"^(no|not|disable|dont|skip|without)[_A-Z-]", re.I)
STOPWORDS = set(
    [
        "a",
        "an",
        "the",
        "to",
        "of",
        "for",
        "and",
        "or",
        "in",
        "on",
        "with",
        "by",
        "from",
        "this",
        "that",
        "is",
        "are",
        "be",
        "it",
        "as",
        "at",
        "use",
        "when",
        "tool",
        "returns",
        "return",
        "get",
        "given",
        "user",
    ]
)
MIN_TOOL_DESC = 40
MIN_PARAM_DESC = 12
MAX_PARAMS = 12


def extract_tools(doc) -> list[dict]:
    if isinstance(doc, dict):
        for key in ("tools", "functions"):
            if isinstance(doc.get(key), list):
                return [normalise(t) for t in doc[key]]
        return [normalise(doc)]
    if isinstance(doc, list):
        return [normalise(t) for t in doc]
    raise ValueError("expected a JSON object or list of tools")


def normalise(tool) -> dict:
    if not isinstance(tool, dict):
        return {"name": None, "description": None, "schema": None, "raw": tool}
    if isinstance(tool.get("function"), dict):
        tool = tool["function"]
    schema = None
    for key in ("parameters", "input_schema", "inputSchema", "schema"):
        if key in tool:
            schema = tool[key]
            break
    return {"name": tool.get("name"), "description": tool.get("description"), "schema": schema}


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOPWORDS and len(w) > 2}


def lint_property(tool: str, path: str, prop, findings: list[dict], depth: int = 0) -> None:
    def add(sev: str, code: str, msg: str) -> None:
        findings.append({"severity": sev, "tool": tool, "path": path, "code": code, "message": msg})

    if not isinstance(prop, dict):
        add("high", "invalid-property", "property schema must be an object")
        return
    ptype = prop.get("type")
    has_combinator = any(k in prop for k in ("anyOf", "oneOf", "allOf", "$ref", "enum", "const"))
    if ptype is None and not has_combinator:
        add("medium", "missing-type", "property has no 'type'")
    desc = prop.get("description")
    leaf = path.rsplit(".", 1)[-1]
    if not desc:
        sev = "medium" if depth == 0 else "low"
        add(sev, "missing-param-description", "parameter has no description; say what it is and its format")
    elif len(desc.strip()) < MIN_PARAM_DESC:
        add("low", "short-param-description", f"description '{desc.strip()}' is too short to be useful")
    if leaf.lower() in AMBIGUOUS_PARAMS:
        add("medium", "ambiguous-name", f"parameter name '{leaf}' is ambiguous; name what it holds")
    if ptype == "string" and "enum" not in prop and desc and ENUM_HINT_RE.search(desc):
        add("medium", "enum-candidate", "description lists allowed values; use 'enum' instead")
    if "enum" in prop:
        enum = prop["enum"]
        if not isinstance(enum, list) or not enum:
            add("high", "empty-enum", "'enum' must be a non-empty list")
        elif len(set(map(str, enum))) != len(enum):
            add("low", "duplicate-enum", "'enum' has duplicate values")
    if ptype == "boolean" and NEGATIVE_BOOL_RE.match(leaf):
        add(
            "low",
            "negative-boolean",
            f"'{leaf}' is a negated flag; prefer a positive name (double negatives)",
        )
    if (
        ptype in ("integer", "number")
        and desc
        and re.search(r"\b(between|max|min|up to|at most)\b", desc, re.I)
    ):
        if "minimum" not in prop and "maximum" not in prop:
            add("low", "range-in-prose", "description states a range; add 'minimum'/'maximum'")
    if ptype == "string" and desc and re.search(r"\b(date|time|timestamp|iso.?8601)\b", desc, re.I):
        if "format" not in prop and "pattern" not in prop and not re.search(r"YYYY|ISO", desc):
            add("low", "date-format", "date/time parameter without 'format' or an example format")
    if ptype == "array":
        items = prop.get("items")
        if not isinstance(items, dict):
            add("medium", "array-without-items", "array parameter has no 'items' schema")
        else:
            lint_property(tool, f"{path}[]", items, findings, depth + 1)
    if ptype == "object":
        lint_object(tool, path, prop, findings, depth + 1)


def lint_object(tool: str, path: str, schema: dict, findings: list[dict], depth: int) -> None:
    def add(sev: str, code: str, msg: str) -> None:
        findings.append({"severity": sev, "tool": tool, "path": path, "code": code, "message": msg})

    props = schema.get("properties")
    if props is None:
        if depth == 0:
            return
        add("low", "open-object", "object parameter has no 'properties'; the model will guess its shape")
        return
    if not isinstance(props, dict):
        add("high", "invalid-properties", "'properties' must be an object")
        return
    required = schema.get("required")
    if required is None:
        if props:
            add("medium", "missing-required", "no 'required' list; say which parameters are mandatory")
        required = []
    elif not isinstance(required, list):
        add("high", "invalid-required", "'required' must be a list")
        required = []
    for name in required:
        if name not in props:
            add("high", "unknown-required", f"'required' lists '{name}' which is not a property")
    if schema.get("additionalProperties") is not False and props:
        add("info", "additional-properties", "set 'additionalProperties': false to reject invented fields")
    if depth == 0 and len(props) > MAX_PARAMS:
        add("medium", "too-many-params", f"{len(props)} parameters; split the tool or group options")
    if depth > 2:
        add("low", "deep-nesting", "schema nested more than 3 levels; flatten it")
    for pname, prop in props.items():
        lint_property(tool, f"{path}.{pname}" if path else pname, prop, findings, depth)


def lint_tools(tools: list[dict], overlap: float = 0.6) -> list[dict]:
    tools = [t if isinstance(t, dict) and "schema" in t else normalise(t) for t in tools]
    findings: list[dict] = []
    seen: dict[str, int] = {}
    for i, tool in enumerate(tools):
        name = tool.get("name")
        label = name if isinstance(name, str) and name else f"#{i}"

        def add(sev: str, code: str, msg: str, label=label) -> None:
            findings.append({"severity": sev, "tool": label, "path": "", "code": code, "message": msg})

        if not isinstance(name, str) or not name:
            add("high", "missing-name", "tool has no name")
        else:
            if not NAME_RE.match(name):
                add("high", "invalid-name", "use letters, digits, '_' or '-', start with a letter, max 64")
            if name in seen:
                add("high", "duplicate-name", f"name also used by tool #{seen[name]}")
            seen.setdefault(name, i)
            if re.fullmatch(r"(do|run|execute|handle|process|tool|helper|action)\w*", name, re.I):
                add("medium", "vague-name", "name does not say what the tool does (verb + object)")
        desc = tool.get("description")
        if not isinstance(desc, str) or not desc.strip():
            add(
                "high",
                "missing-description",
                "tool has no description; the model cannot tell when to call it",
            )
        else:
            if len(desc.strip()) < MIN_TOOL_DESC:
                add(
                    "medium",
                    "short-description",
                    "description is too short; say what, when and what it returns",
                )
            if not re.search(r"\b(use|call|when|if|for)\b", desc, re.I):
                add("low", "no-when", "description does not say when to use the tool")
        schema = tool.get("schema")
        if schema is None:
            add(
                "medium",
                "missing-schema",
                "no parameters schema; use an empty object schema if it takes none",
            )
            continue
        if not isinstance(schema, dict):
            add("high", "invalid-schema", "parameters schema must be an object")
            continue
        if schema.get("type") != "object":
            add("high", "root-not-object", "parameters schema 'type' must be 'object'")
        lint_object(label, "", schema, findings, 0)

    # Overlapping descriptions confuse tool selection.
    for i in range(len(tools)):
        for j in range(i + 1, len(tools)):
            a, b = words(tools[i].get("description") or ""), words(tools[j].get("description") or "")
            if len(a) < 4 or len(b) < 4:
                continue
            score = len(a & b) / len(a | b)
            if score >= overlap:
                findings.append(
                    {
                        "severity": "medium",
                        "tool": f"{tools[i].get('name')}, {tools[j].get('name')}",
                        "path": "",
                        "code": "overlapping-tools",
                        "message": f"descriptions are {score:.0%} similar; say how they differ",
                    }
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Lint JSON Schema tool/function definitions for LLM agents.")
    p.add_argument("files", nargs="+", type=Path, help="JSON files with tool definitions ('-' for stdin)")
    p.add_argument("--json", action="store_true", help="print findings as JSON")
    p.add_argument("--fail-on", choices=SEVERITIES, default="medium", help="lowest severity that exits 1")
    p.add_argument("--min-severity", choices=SEVERITIES, default="info", help="hide findings below this")
    p.add_argument("--overlap", type=float, default=0.6, help="description similarity threshold (0-1)")
    args = p.parse_args(argv)

    tools: list[dict] = []
    for f in args.files:
        try:
            text = sys.stdin.read() if str(f) == "-" else f.read_text(encoding="utf-8")
            tools += extract_tools(json.loads(text))
        except (OSError, ValueError) as exc:
            print(f"error: {f}: {exc}", file=sys.stderr)
            return 2
    findings = lint_tools(tools, args.overlap)
    shown = [x for x in findings if SEVERITIES.index(x["severity"]) >= SEVERITIES.index(args.min_severity)]
    shown.sort(key=lambda x: (-SEVERITIES.index(x["severity"]), x["tool"], x["path"]))
    failing = [x for x in findings if SEVERITIES.index(x["severity"]) >= SEVERITIES.index(args.fail_on)]
    if args.json:
        counts = {s: sum(1 for x in findings if x["severity"] == s) for s in SEVERITIES}
        print(json.dumps({"tools": len(tools), "counts": counts, "findings": shown}, indent=2))
    else:
        for x in shown:
            where = f"{x['tool']}" + (f" {x['path']}" if x["path"] else "")
            print(f"[{x['severity'].upper():6}] {where}: {x['message']} ({x['code']})")
        print(
            f"\n{len(tools)} tool(s), {len(findings)} finding(s), {len(failing)} at or above {args.fail_on}"
        )
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
