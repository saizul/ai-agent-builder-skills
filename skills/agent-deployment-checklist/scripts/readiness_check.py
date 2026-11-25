#!/usr/bin/env python3
"""Score a filled-in launch checklist (assets/launch-checklist.md) and decide go / no-go.

Checklist items are Markdown task-list lines with a severity tag:
  - [x] [BLOCKER] Rollback path tested ...
  - [ ] [MAJOR] Dashboards for handover rate ...
  - [~] [MINOR] Status page entry (n/a: internal tool)
"[x]" = done, "[ ]" = open, "[~]" or "(n/a: reason)" = not applicable (needs a reason).
Lines may end with "-- evidence: <link or note>"; --require-evidence makes
BLOCKER items without evidence count as open.

Decision: any open BLOCKER = NO-GO; open MAJOR items = GO WITH SIGN-OFF
(exit 1 unless --allow-major); otherwise GO.

Exit codes: 0 = GO (or sign-off allowed), 1 = NO-GO / sign-off needed, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ITEM_RE = re.compile(
    r"^\s*[-*]\s+\[(?P<mark>[ xX~-])\]\s+(?:\[(?P<sev>BLOCKER|MAJOR|MINOR)\]\s*)?(?P<text>.+)$"
)
NA_RE = re.compile(r"\(n/?a(?::\s*(?P<reason>[^)]*))?\)", re.I)
EVIDENCE_RE = re.compile(r"--\s*evidence:\s*(?P<ev>\S.*)$", re.I)


def parse(text: str) -> list[dict]:
    items = []
    section = "General"
    for n, line in enumerate(text.splitlines(), 1):
        h = re.match(r"^#{2,4}\s+(.+?)\s*$", line)
        if h:
            section = h.group(1)
            continue
        m = ITEM_RE.match(line)
        if not m:
            continue
        body = m.group("text").strip()
        mark = m.group("mark").lower()
        na = NA_RE.search(body)
        ev = EVIDENCE_RE.search(body)
        evidence = ev.group("ev").strip() if ev else ""
        if evidence.startswith("<") and evidence.endswith(">"):
            evidence = ""
        if mark in ("~", "-") or (na and mark != " "):
            state = "na"
        elif mark == "x":
            state = "done"
        else:
            state = "open"
        items.append(
            {
                "line": n,
                "section": section,
                "severity": (m.group("sev") or "MINOR").lower(),
                "text": EVIDENCE_RE.sub("", body).strip(),
                "state": state,
                "na_reason": (na.group("reason") or "").strip() if na else "",
                "evidence": evidence,
            }
        )
    return items


def decide(items: list[dict], require_evidence: bool = False) -> dict:
    problems = []
    for it in items:
        if it["state"] == "na" and not it["na_reason"]:
            problems.append({**it, "problem": "marked not applicable without a reason"})
            it["state"] = "open"
        if require_evidence and it["severity"] == "blocker" and it["state"] == "done" and not it["evidence"]:
            problems.append({**it, "problem": "blocker marked done without evidence"})
            it["state"] = "open"
    open_items = [i for i in items if i["state"] == "open"]
    open_blockers = [i for i in open_items if i["severity"] == "blocker"]
    open_majors = [i for i in open_items if i["severity"] == "major"]
    if not items or open_blockers:
        decision = "NO-GO"
    elif open_majors:
        decision = "GO WITH SIGN-OFF"
    else:
        decision = "GO"
    by_section = defaultdict(lambda: {"done": 0, "open": 0, "na": 0})
    for i in items:
        by_section[i["section"]][i["state"]] += 1
    applicable = [i for i in items if i["state"] != "na"]
    done = sum(1 for i in applicable if i["state"] == "done")
    return {
        "decision": decision,
        "items": len(items),
        "done": done,
        "open": len(open_items),
        "not_applicable": len(items) - len(applicable),
        "completion": round(done / len(applicable), 4) if applicable else 0.0,
        "open_blockers": [
            {"line": i["line"], "section": i["section"], "text": i["text"]} for i in open_blockers
        ],
        "open_majors": [{"line": i["line"], "section": i["section"], "text": i["text"]} for i in open_majors],
        "open_minors": [
            {"line": i["line"], "section": i["section"], "text": i["text"]}
            for i in open_items
            if i["severity"] == "minor"
        ],
        "problems": [{"line": p["line"], "text": p["text"], "problem": p["problem"]} for p in problems],
        "by_section": dict(by_section),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score an agent launch checklist and decide go / no-go.")
    p.add_argument("checklist", type=Path, help="filled-in checklist Markdown")
    p.add_argument("--require-evidence", action="store_true", help="BLOCKER items need '-- evidence: ...'")
    p.add_argument("--allow-major", action="store_true", help="exit 0 for GO WITH SIGN-OFF")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        items = parse(args.checklist.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rep = decide(items, args.require_evidence)
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"Decision: {rep['decision']}")
        print(
            f"{rep['done']}/{rep['items'] - rep['not_applicable']} applicable items done "
            f"({rep['completion']:.0%}), {rep['not_applicable']} n/a"
        )
        for label, key in (("BLOCKER", "open_blockers"), ("MAJOR", "open_majors"), ("MINOR", "open_minors")):
            for i in rep[key]:
                print(f"  open [{label}] line {i['line']} ({i['section']}): {i['text']}")
        for pr in rep["problems"]:
            print(f"  problem line {pr['line']}: {pr['problem']}: {pr['text']}")
        if not items:
            print("No checklist items found (expected '- [ ] [BLOCKER] ...' lines).")
    if rep["decision"] == "GO":
        return 0
    if rep["decision"] == "GO WITH SIGN-OFF" and args.allow_major:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
