#!/usr/bin/env python3
"""Scan retrieved or user-supplied content for prompt-injection red flags.

Use it on documents before they are indexed for retrieval, on web pages or
emails an agent will read, and on tool results. It is a heuristic tripwire,
not a guarantee: a clean scan does not prove content is safe.

Flags: instructions aimed at the model ("ignore previous instructions",
"you are now", "new system prompt"), fake role/turn markers, requests to
reveal the system prompt or secrets, instructions to call tools, send data
or open links, markdown images/links that carry data in the query string,
hidden text (zero-width characters, bidi overrides, HTML hidden by CSS or
comments), and long base64 blobs.

Input: files, directories (.txt .md .html .json .jsonl .csv .eml), or '-'.
Each file gets a score (sum of rule weights); --threshold sets "suspicious".

Exit codes: 0 = nothing at or above --threshold, 1 = suspicious content, 2 = error.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

EXTS = {".txt", ".md", ".markdown", ".html", ".htm", ".json", ".jsonl", ".csv", ".eml", ".xml"}

ZERO_WIDTH = "[\u200b\u200c\u200d\u2060\ufeff\u00ad]"
BIDI = "[\u202a-\u202e\u2066-\u2069]"

# (code, weight, description, regex)
RULES: list[tuple[str, int, str, re.Pattern]] = [
    (
        "override-instructions",
        5,
        "tries to override earlier instructions",
        re.compile(
            r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|"
            r"your|the system)\b[^.\n]{0,30}\b(instructions?|prompts?|rules|guidelines|directions)\b",
            re.I,
        ),
    ),
    (
        "role-reassignment",
        4,
        "tries to give the model a new role or mode",
        re.compile(
            r"\b(you are now|from now on,? you (?:are|will)|act as (?:an? )?(?:unrestricted|jailbroken|"
            r"developer mode)|enter (?:developer|debug|god) mode|new (?:system )?instructions?:)",
            re.I,
        ),
    ),
    (
        "fake-role-marker",
        4,
        "contains chat-format role or turn markers",
        re.compile(
            r"(<\|(?:im_start|im_end|system|assistant|user|endoftext)\|>|^\s*#{2,}\s*(?:system|assistant)\s*:?\s*$|"
            r"^\s*(?:system|assistant)\s*:\s|\[/?INST\]|<</?SYS>>|</?(?:system|instructions?)>)",
            re.I | re.M,
        ),
    ),
    (
        "prompt-exfiltration",
        4,
        "asks to reveal the system prompt, instructions or secrets",
        re.compile(
            r"\b(reveal|print|show|repeat|output|tell me|leak)\b[^.\n]{0,40}\b(system prompt|your "
            r"instructions|hidden instructions|initial prompt|api keys?|credentials|passwords?|secrets?)\b",
            re.I,
        ),
    ),
    (
        "tool-instruction",
        3,
        "tells the model to call a tool or take an action",
        re.compile(
            r"\b(call|invoke|use|run|execute|trigger)\b[^.\n]{0,20}\b(the )?(tool|function|plugin|action|"
            r"command)\b[^.\n]{0,40}\b(with|to|and)\b",
            re.I,
        ),
    ),
    (
        "data-exfiltration",
        4,
        "asks to send, forward or upload data somewhere",
        re.compile(
            r"\b(send|forward|email|upload|post|transmit|exfiltrate)\b[^.\n]{0,50}\b(to|at)\b[^.\n]{0,20}"
            r"(https?://|[\w.+-]+@[\w-]+\.[\w.]+|webhook)",
            re.I,
        ),
    ),
    (
        "markdown-exfil-link",
        4,
        "markdown image or link with data-like query parameters",
        re.compile(
            r"!?\[[^\]]*\]\(\s*https?://[^)\s]+\?[^)\s]*(?:=\{|=%7B|=\$|data=|q=|secret|token|prompt)", re.I
        ),
    ),
    (
        "do-not-tell-user",
        3,
        "asks the model to hide something from the user",
        re.compile(
            r"\b(do not|don't|never)\b[^.\n]{0,20}\b(tell|inform|mention|reveal|show)\b[^.\n]{0,20}\b"
            r"(the )?user\b",
            re.I,
        ),
    ),
    ("zero-width", 3, "zero-width or invisible characters", re.compile(ZERO_WIDTH)),
    ("bidi-override", 4, "bidirectional override characters", re.compile(BIDI)),
    (
        "hidden-html",
        3,
        "HTML hidden by CSS (display:none, font-size:0, white text, off-screen)",
        re.compile(
            r"style\s*=\s*[\"'][^\"']*(display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|"
            r"color\s*:\s*(?:#fff(?:fff)?|white)\b|left\s*:\s*-\d{3,}px|opacity\s*:\s*0(?:\.0+)?\b)",
            re.I,
        ),
    ),
    (
        "html-comment-instruction",
        3,
        "instruction-like text inside an HTML comment",
        re.compile(
            r"<!--(?:(?!-->).){0,400}?\b(ignore|assistant|AI|model|instructions?|prompt)\b", re.I | re.S
        ),
    ),
    (
        "base64-blob",
        1,
        "long base64-looking blob",
        re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{120,}={0,2}"),
    ),
]


def scan_text(text: str) -> list[dict]:
    # Decode HTML entities so encoded payloads (&#8203;, &lt;|im_start|&gt;) are seen too.
    text = html.unescape(text)
    hits = []
    for code, weight, desc, rx in RULES:
        matches = list(rx.finditer(text))
        if not matches:
            continue
        m = matches[0]
        line = text.count("\n", 0, m.start()) + 1
        snippet = text[max(0, m.start() - 30) : m.end() + 30].replace("\n", " ")
        snippet = re.sub(BIDI, "<?>", re.sub(ZERO_WIDTH, "<?>", snippet))
        hits.append(
            {
                "code": code,
                "weight": weight,
                "description": desc,
                "count": len(matches),
                "line": line,
                "snippet": snippet[:140],
            }
        )
    return hits


def collect(inputs: list[str]) -> list[tuple[str, str]]:
    out = []
    for item in inputs:
        if item == "-":
            out.append(("<stdin>", sys.stdin.read()))
            continue
        p = Path(item)
        if p.is_dir():
            files = sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in EXTS)
        elif p.is_file():
            files = [p]
        else:
            raise FileNotFoundError(item)
        out += [(f.as_posix(), f.read_text(encoding="utf-8", errors="replace")) for f in files]
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scan content for prompt-injection red flags.")
    p.add_argument("inputs", nargs="+", help="files, directories or '-'")
    p.add_argument("--threshold", type=int, default=4, help="score that counts as suspicious (default 4)")
    p.add_argument("--jsonl-field", help="treat files as JSONL and scan this field per record (e.g. text)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--all", action="store_true", help="also list clean items")
    args = p.parse_args(argv)
    try:
        docs = collect(args.inputs)
    except (OSError, FileNotFoundError) as exc:
        print(f"error: not found or unreadable: {exc}", file=sys.stderr)
        return 2
    items = []
    for name, text in docs:
        if args.jsonl_field:
            for n, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    print(f"error: {name}:{n} is not JSON", file=sys.stderr)
                    return 2
                rid = rec.get("id", n) if isinstance(rec, dict) else n
                value = rec.get(args.jsonl_field, "") if isinstance(rec, dict) else ""
                items.append((f"{name}#{rid}", str(value)))
        else:
            items.append((name, text))
    results = []
    for name, text in items:
        hits = scan_text(text)
        score = sum(h["weight"] for h in hits)
        results.append({"item": name, "score": score, "suspicious": score >= args.threshold, "hits": hits})
    flagged = [r for r in results if r["suspicious"]]
    if args.json:
        print(json.dumps({"scanned": len(results), "suspicious": len(flagged), "results": results}, indent=2))
    else:
        for r in sorted(results, key=lambda r: -r["score"]):
            if not r["hits"] and not args.all:
                continue
            label = "SUSPICIOUS" if r["suspicious"] else "review" if r["hits"] else "clean"
            print(f"[{label}] {r['item']} score={r['score']}")
            for h in r["hits"]:
                print(f"    {h['code']} x{h['count']} (line {h['line']}): {h['snippet']}")
        print(f"\n{len(results)} item(s) scanned, {len(flagged)} suspicious (threshold {args.threshold})")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
