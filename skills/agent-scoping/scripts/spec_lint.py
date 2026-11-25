#!/usr/bin/env python3
"""Check an agent spec (Markdown, from assets/agent-spec-template.md) for gaps.

Checks that the required sections exist and are filled in (not empty, not
template placeholders), and that the content is specific enough to build
and test against:
  * at least one out-of-scope item
  * every tool row has an access level, and write/act tools state whether
    the user must confirm
  * at least one handover trigger with a destination
  * every KPI has a numeric target and a measurement method
  * at least one evaluation scenario and one risk

Sections are found by keyword, so numbering and extra sections are fine.

Exit codes: 0 = ready (no blocking gaps), 1 = gaps found, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# key: (heading keywords regex, severity if missing)
SECTIONS = {
    "goal": (r"goal|objective|problem", "blocker"),
    "users": (r"users?|channels?|audience", "major"),
    "in_scope": (r"in[ -]scope|tasks|jobs", "blocker"),
    "out_of_scope": (r"out[ -]of[ -]scope|non[- ]goals", "blocker"),
    "tools": (r"tools?|data access|integrations?", "blocker"),
    "handover": (r"hand ?over|hand ?off|escalation", "blocker"),
    "guardrails": (r"guardrails?|policies|policy|safety|compliance", "major"),
    "kpis": (r"kpis?|metrics|success", "blocker"),
    "evaluation": (r"evaluation|eval|test plan|acceptance", "major"),
    "risks": (r"risks?|open questions|assumptions", "minor"),
    "rollout": (r"rollout|launch|pilot|deployment", "minor"),
}
PLACEHOLDER_RE = re.compile(r"(<[^>\n]{2,60}>|\bTODO\b|\bTBD\b|\bXXX\b|\.\.\.\s*$|^\s*-\s*$)", re.M)
WRITE_RE = re.compile(
    r"\b(write|create|update|delete|send|act|refund|book|cancel|pay|charge|modify|post)\b", re.I
)
YES_NO_RE = re.compile(r"\b(yes|no|always|never|over|above|required|not required|n/?a)\b", re.I)


def parse_sections(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        m = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if m:
            out.append((m.group(1), []))
        elif out:
            out[-1][1].append(line)
    return [(h, "\n".join(b).strip()) for h, b in out]


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


def table_rows(body: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return [], []
    header = [c.strip().lower() for c in lines[0].strip("|").split("|")]
    rows = []
    for ln in lines[1:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        if any(cells):
            rows.append(cells + [""] * (len(header) - len(cells)))
    return header, rows


def col(header: list[str], *names: str) -> int | None:
    for i, h in enumerate(header):
        if any(n in h for n in names):
            return i
    return None


def is_placeholder(cell: str) -> bool:
    return not cell.strip() or bool(PLACEHOLDER_RE.search(cell)) or cell.strip() in {"-", "?"}


def items(body: str) -> list[str]:
    lines = [re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", ln).strip() for ln in body.splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("|") and not is_placeholder(ln)]


def lint(text: str) -> dict:
    findings: list[dict] = []

    def add(sev: str, section: str, msg: str) -> None:
        findings.append({"severity": sev, "section": section, "message": msg})

    sections = parse_sections(text)
    found: dict[str, str] = {}
    for key, (rx, _sev) in SECTIONS.items():
        for heading, body in sections:
            if re.search(rf"\b(?:{rx})\b", heading, re.I) and key not in found:
                if key == "in_scope" and re.search(r"out", heading, re.I):
                    continue
                if key == "tools" and re.search(r"kpi|metric", heading, re.I):
                    continue
                found[key] = strip_comments(body)
                break
    for key, (_rx, sev) in SECTIONS.items():
        if key not in found:
            add(sev, key, "section is missing")
            continue
        body = found[key]
        if not body or not re.sub(r"[|\-:\s]", "", body):
            add(sev, key, "section is empty")
        elif PLACEHOLDER_RE.search(body) and len(items(body)) == 0 and not table_rows(body)[1]:
            add(sev, key, "section still contains only template placeholders")
        elif PLACEHOLDER_RE.search(body):
            add("minor", key, "section contains unfilled placeholders (<...>, TODO, TBD)")

    if "out_of_scope" in found and not items(found["out_of_scope"]):
        add("blocker", "out_of_scope", "list at least one thing the agent must not do or answer")

    if "tools" in found:
        header, rows = table_rows(found["tools"])
        if not rows:
            add("major", "tools", "no tools table; list each tool with access level and confirmation rule")
        a_col, c_col = col(header, "access", "read/write", "permission"), col(header, "confirm", "approval")
        for r in rows:
            name = r[0] or "?"
            if is_placeholder(name):
                add("minor", "tools", "tool row without a name")
                continue
            access = r[a_col] if a_col is not None and a_col < len(r) else ""
            if is_placeholder(access):
                add("major", "tools", f"tool '{name}' has no access level (read / write)")
            if WRITE_RE.search(access) or WRITE_RE.search(name):
                conf = r[c_col] if c_col is not None and c_col < len(r) else ""
                if is_placeholder(conf) or not YES_NO_RE.search(conf):
                    add(
                        "blocker",
                        "tools",
                        f"tool '{name}' can change data; state whether the user must confirm",
                    )

    if "handover" in found:
        header, rows = table_rows(found["handover"])
        real = [r for r in rows if not is_placeholder(r[0])]
        if not real and not items(found["handover"]):
            add("blocker", "handover", "no handover triggers defined")
        to_col = col(header, "to", "destination", "route", "queue", "team")
        for r in real:
            if to_col is not None and to_col < len(r) and is_placeholder(r[to_col]):
                add("major", "handover", f"handover trigger '{r[0]}' has no destination")

    if "kpis" in found:
        header, rows = table_rows(found["kpis"])
        real = [r for r in rows if not is_placeholder(r[0])]
        if not real:
            add("blocker", "kpis", "no KPI table rows; define KPIs with baseline, target and measurement")
        t_col, m_col = col(header, "target", "goal"), col(header, "measure", "how", "source")
        for r in real:
            target = r[t_col] if t_col is not None and t_col < len(r) else ""
            if not re.search(r"\d", target):
                add("major", "kpis", f"KPI '{r[0]}' has no numeric target")
            if m_col is not None and m_col < len(r) and is_placeholder(r[m_col]):
                add("major", "kpis", f"KPI '{r[0]}' has no measurement method")

    if "evaluation" in found and not items(found["evaluation"]) and not table_rows(found["evaluation"])[1]:
        add("major", "evaluation", "list at least one evaluation scenario or acceptance test")

    order = {"blocker": 0, "major": 1, "minor": 2}
    findings.sort(key=lambda f: order[f["severity"]])
    blockers = sum(1 for f in findings if f["severity"] == "blocker")
    majors = sum(1 for f in findings if f["severity"] == "major")
    return {
        "sections_found": sorted(found),
        "sections_missing": [k for k in SECTIONS if k not in found],
        "ready": blockers == 0 and majors == 0,
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check an agent spec Markdown file for gaps.")
    p.add_argument("spec", type=Path, help="agent spec Markdown file")
    p.add_argument("--allow-major", action="store_true", help="only blockers make the exit code 1")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        text = args.spec.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rep = lint(text)
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        for f in rep["findings"]:
            print(f"[{f['severity'].upper():7}] {f['section']}: {f['message']}")
        state = "READY" if rep["ready"] else "NOT READY"
        print(
            f"\n{state}: {len(rep['findings'])} finding(s); "
            f"sections found: {', '.join(rep['sections_found'])}"
        )
    blocking = [
        f
        for f in rep["findings"]
        if f["severity"] == "blocker" or (f["severity"] == "major" and not args.allow_major)
    ]
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
