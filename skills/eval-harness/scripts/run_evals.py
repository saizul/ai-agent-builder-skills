#!/usr/bin/env python3
"""Score recorded LLM/agent outputs against a JSONL eval set.

cases.jsonl, one test case per line:
  {"id": "refund-1", "input": "...", "tags": ["refunds"],
   "checks": [{"type": "contains", "value": "14 days"},
              {"type": "not_contains", "value": "guarantee", "ignore_case": true},
              {"type": "regex", "pattern": "order #\\\\d+"},
              {"type": "exact", "value": "yes"},
              {"type": "one_of", "values": ["yes", "no"]},
              {"type": "max_chars", "value": 600},
              {"type": "json_field", "path": "action", "value": "handover"},
              {"type": "tool_called", "value": "lookup_order"},
              {"type": "rubric", "criteria": [
                  {"id": "polite", "keywords": ["sorry", "apolog"]},
                  {"id": "accurate-policy"}]}]}

outputs.jsonl, one recorded output per line:
  {"id": "refund-1", "output": "...", "tool_calls": ["lookup_order"]}

Rubric criteria with "keywords" are scored automatically (any keyword,
case-insensitive). Criteria without keywords need a grade: export them with
--review-out, grade them (human or a separate judge model), and pass the
grades back with --grades ({"id", "criterion", "pass"} per line). Ungraded
criteria count as "needs_review", not as passes.

--baseline PREVIOUS_RESULTS.json reports regressions (cases that passed before
and fail now). --min-pass-rate exits 1 when the pass rate is lower.

Exit codes: 0 = ok, 1 = below --min-pass-rate or regressions with
--fail-on-regression, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{n}: invalid JSON: {exc.msg}") from exc
    return rows


def get_path(obj, path: str):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


def _fold(text: str, check: dict) -> str:
    return text.lower() if check.get("ignore_case", True) else text


def run_check(check: dict, record: dict, grades: dict, case_id: str) -> tuple[str, str]:
    """Return (status, detail) where status is pass, fail or needs_review."""
    output = str(record.get("output", ""))
    ctype = check.get("type")
    if ctype == "exact":
        a, b = output.strip(), str(check["value"]).strip()
        ok = a.lower() == b.lower() if check.get("ignore_case", False) else a == b
        return ("pass" if ok else "fail"), f"expected exactly {b!r}"
    if ctype in ("contains", "not_contains"):
        vals = check.get("values") or [check["value"]]
        hits = [v for v in vals if _fold(str(v), check) in _fold(output, check)]
        if ctype == "contains":
            need_all = check.get("all", True)
            ok = len(hits) == len(vals) if need_all else bool(hits)
            missing = [v for v in vals if v not in hits]
            return ("pass" if ok else "fail"), f"missing {missing}" if not ok else "found"
        return ("pass" if not hits else "fail"), f"found forbidden {hits}" if hits else "absent"
    if ctype == "one_of":
        ok = _fold(output.strip(), check) in {_fold(str(v), check) for v in check["values"]}
        return ("pass" if ok else "fail"), f"expected one of {check['values']}"
    if ctype == "regex":
        flags = re.I if check.get("ignore_case") else 0
        ok = re.search(check["pattern"], output, flags | re.S) is not None
        if check.get("negate"):
            ok = not ok
        return ("pass" if ok else "fail"), f"pattern {check['pattern']!r}"
    if ctype in ("max_chars", "min_chars"):
        n = len(output)
        ok = n <= int(check["value"]) if ctype == "max_chars" else n >= int(check["value"])
        return ("pass" if ok else "fail"), f"{n} chars"
    if ctype == "json_field":
        try:
            data = json.loads(output)
            val = get_path(data, check["path"])
        except (json.JSONDecodeError, KeyError):
            return "fail", f"output is not JSON with field {check['path']!r}"
        if "value" in check:
            return ("pass" if val == check["value"] else "fail"), f"{check['path']}={val!r}"
        return "pass", f"{check['path']} present"
    if ctype in ("tool_called", "tool_not_called"):
        calls = record.get("tool_calls") or []
        names = [c.get("name") if isinstance(c, dict) else c for c in calls]
        called = check["value"] in names
        ok = called if ctype == "tool_called" else not called
        return ("pass" if ok else "fail"), f"tool calls: {names}"
    if ctype == "rubric":
        statuses, details = [], []
        for crit in check.get("criteria", []):
            cid = crit.get("id", "criterion")
            if crit.get("keywords"):
                ok = any(k.lower() in output.lower() for k in crit["keywords"])
                statuses.append("pass" if ok else "fail")
            elif (case_id, cid) in grades:
                statuses.append("pass" if grades[(case_id, cid)] else "fail")
            else:
                statuses.append("needs_review")
            details.append(f"{cid}:{statuses[-1]}")
        if "fail" in statuses:
            return "fail", ", ".join(details)
        if "needs_review" in statuses:
            return "needs_review", ", ".join(details)
        return "pass", ", ".join(details)
    raise ValueError(f"unknown check type {ctype!r}")


def evaluate(cases: list[dict], outputs: list[dict], grades_rows: list[dict] | None = None) -> dict:
    grades = {(g["id"], g["criterion"]): bool(g["pass"]) for g in grades_rows or []}
    by_id = {o["id"]: o for o in outputs}
    results = []
    for case in cases:
        cid = case["id"]
        rec = by_id.get(cid)
        if rec is None:
            results.append(
                {"id": cid, "status": "missing_output", "tags": case.get("tags", []), "checks": []}
            )
            continue
        checks = []
        for check in case.get("checks", []):
            status, detail = run_check(check, rec, grades, cid)
            checks.append({"type": check.get("type"), "status": status, "detail": detail})
        statuses = {c["status"] for c in checks}
        status = "fail" if "fail" in statuses else "needs_review" if "needs_review" in statuses else "pass"
        if not checks:
            status = "needs_review"
        results.append({"id": cid, "status": status, "tags": case.get("tags", []), "checks": checks})
    total = len(results)
    counts = defaultdict(int)
    for r in results:
        counts[r["status"]] += 1
    tag_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "pass": 0})
    for r in results:
        for t in r["tags"] or ["untagged"]:
            tag_stats[t]["total"] += 1
            tag_stats[t]["pass"] += r["status"] == "pass"
    scored = total - counts["needs_review"]
    return {
        "total": total,
        "counts": dict(counts),
        "pass_rate": round(counts["pass"] / total, 4) if total else 0.0,
        "pass_rate_scored": round(counts["pass"] / scored, 4) if scored else 0.0,
        "by_tag": {
            t: {**v, "pass_rate": round(v["pass"] / v["total"], 4)} for t, v in sorted(tag_stats.items())
        },
        "unknown_outputs": sorted(set(by_id) - {c["id"] for c in cases}),
        "results": results,
    }


def review_rows(cases: list[dict], outputs: list[dict]) -> list[dict]:
    by_id = {o["id"]: o for o in outputs}
    rows = []
    for case in cases:
        for check in case.get("checks", []):
            if check.get("type") != "rubric":
                continue
            for crit in check.get("criteria", []):
                if crit.get("keywords"):
                    continue
                rows.append(
                    {
                        "id": case["id"],
                        "criterion": crit.get("id", "criterion"),
                        "guidance": crit.get("description", ""),
                        "input": case.get("input", ""),
                        "output": by_id.get(case["id"], {}).get("output", ""),
                        "pass": None,
                    }
                )
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score recorded outputs against a JSONL eval set.")
    p.add_argument("cases", type=Path, help="cases JSONL")
    p.add_argument("outputs", type=Path, help="recorded outputs JSONL ({id, output, tool_calls?})")
    p.add_argument("--grades", type=Path, help="JSONL grades for rubric criteria ({id, criterion, pass})")
    p.add_argument("--review-out", type=Path, help="write ungraded rubric items to this JSONL file")
    p.add_argument("--baseline", type=Path, help="previous --json results to compare against")
    p.add_argument("--min-pass-rate", type=float, help="exit 1 when pass rate (0-1) is below this")
    p.add_argument("--fail-on-regression", action="store_true", help="exit 1 when a case regressed")
    p.add_argument("--tag", action="append", help="only run cases with this tag (repeatable)")
    p.add_argument("--json", action="store_true", help="print full results as JSON")
    args = p.parse_args(argv)
    try:
        cases = read_jsonl(args.cases)
        outputs = read_jsonl(args.outputs)
        grades = read_jsonl(args.grades) if args.grades else []
        baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
        if args.tag:
            cases = [c for c in cases if set(c.get("tags", [])) & set(args.tag)]
        ids = [c.get("id") for c in cases]
        if None in ids or len(ids) != len(set(ids)):
            raise ValueError("every case needs a unique 'id'")
        report = evaluate(cases, outputs, grades)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.review_out:
        rows = [
            r
            for r in review_rows(cases, outputs)
            if (r["id"], r["criterion"]) not in {(g["id"], g["criterion"]) for g in grades}
        ]
        args.review_out.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
        )
    regressions, fixed = [], []
    if baseline:
        before = {r["id"]: r["status"] for r in baseline.get("results", [])}
        for r in report["results"]:
            if before.get(r["id"]) == "pass" and r["status"] == "fail":
                regressions.append(r["id"])
            if before.get(r["id"]) == "fail" and r["status"] == "pass":
                fixed.append(r["id"])
        report["regressions"], report["fixed"] = regressions, fixed
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        c = report["counts"]
        print(
            f"{report['total']} case(s): {c.get('pass', 0)} pass, {c.get('fail', 0)} fail, "
            f"{c.get('needs_review', 0)} needs review, {c.get('missing_output', 0)} missing output"
        )
        print(f"pass rate {report['pass_rate']:.1%} (of scored cases {report['pass_rate_scored']:.1%})")
        for tag, st in report["by_tag"].items():
            print(f"  {tag:24} {st['pass']}/{st['total']}  {st['pass_rate']:.0%}")
        for r in report["results"]:
            if r["status"] != "pass":
                bad = [f"{ch['type']}: {ch['detail']}" for ch in r["checks"] if ch["status"] != "pass"]
                print(f"[{r['status'].upper()}] {r['id']}: {'; '.join(bad) or 'no output recorded'}")
        if report["unknown_outputs"]:
            print(f"outputs without a case: {', '.join(report['unknown_outputs'])}")
        if baseline is not None:
            print(f"regressions: {', '.join(regressions) or 'none'}; fixed: {', '.join(fixed) or 'none'}")
    if args.min_pass_rate is not None and report["pass_rate"] < args.min_pass_rate:
        return 1
    if args.fail_on_regression and regressions:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
