#!/usr/bin/env python3
"""Review a system prompt for common defects before it ships.

Flags: always/never and must/must-not contradictions on the same subject,
missing refusal (out-of-scope) rules, missing handover/escalation rules,
missing output-format guidance, tools mentioned without usage rules,
unfilled template placeholders, hard-coded dates, things that look like
secrets, duplicated sentences, vague filler, excessive capitals, and prompts
that are too long (estimated tokens, about 4 characters per token).

Exit codes: 0 = no findings at or above --fail-on, 1 = findings, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]
STOP = set(
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
        "you",
        "your",
        "user",
        "users",
        "any",
        "all",
        "always",
        "never",
        "must",
        "not",
        "do",
        "don't",
        "dont",
        "should",
        "shouldn't",
        "only",
        "ever",
        "please",
        "make",
        "sure",
        "when",
        "if",
        "they",
        "them",
        "their",
    ]
)
REFUSAL_RE = re.compile(
    r"(\bout of scope\b|\bout-of-scope\b|\brefuse\b|\bdecline\b|\bdo not (?:answer|help|discuss|provide)\b|"
    r"\bdon't (?:answer|help|discuss|provide)\b|\bonly (?:answer|help|discuss)\b|\bnot able to help\b|"
    r"\bunrelated (?:questions|requests|topics)\b|\boff-topic\b)",
    re.I,
)
HANDOVER_RE = re.compile(
    r"(\bhand ?(?:over|off)\b|\bescalat\w+|\btransfer\b.*\b(?:human|agent|team|staff)\b|"
    r"\b(?:human|live) (?:agent|support|operator|colleague)\b|\bcreate a (?:support )?ticket\b|"
    r"\bcontact (?:support|our team)\b)",
    re.I,
)
FORMAT_RE = re.compile(
    r"(\bformat\b|\bmarkdown\b|\bjson\b|\bbullet|\bplain text\b|\bsentences?\b|\bwords?\b|"
    r"\bparagraphs?\b|\bconcise\b|\bbrief\b|\btone\b|\blength\b)",
    re.I,
)
TOOL_MENTION_RE = re.compile(
    r"\b(tools?|functions?|api calls?|lookup_\w+|search_\w+|get_\w+|create_\w+)\b", re.I
)
TOOL_RULE_RE = re.compile(
    r"(\b(?:call|use|invoke|run)\b[^.]{0,60}\b(?:tool|function|lookup_\w+|search_\w+|get_\w+|create_\w+)\b|"
    r"\bbefore (?:calling|using)\b|\bconfirm\b[^.]{0,40}\bbefore\b)",
    re.I,
)
PLACEHOLDER_RE = re.compile(
    r"(\{\{[^}]*\}\}|\$\{[^}]*\}|<\s*(?:insert|your|company|name|todo)[^>]*>|\[(?:insert|todo|tbd|"
    r"company name|your [^\]]+)\]|<[a-z][a-z0-9_-]*(?: [a-z0-9_/-]+)+>|"
    r"\bTODO\b|\bTBD\b|\bXXX\b|\blorem ipsum\b)",
    re.I,
)
DATE_RE = re.compile(
    r"\b(today is|current date is|the date is|as of (?:today|now)|this year is)\b|\b20\d\d-\d\d-\d\d\b",
    re.I,
)
SECRET_RE = re.compile(
    r"(\b(?:api[_ -]?key|secret|password|passwd|token|bearer)\b\s*[:=]\s*\S{8,}|"
    r"\b[A-Za-z0-9_-]*(?:sk|pk|key|tok)[-_][A-Za-z0-9]{20,}\b)",
    re.I,
)
VAGUE_RE = re.compile(
    r"\b(be helpful|as needed|as appropriate|if necessary|do your best|use (?:your )?best judgment|"
    r"etc\.?|and so on|be smart|be careful|try to)\b",
    re.I,
)
POS_RE = re.compile(r"\b(always|must|you will|required to)\b", re.I)
NEG_RE = re.compile(r"\b(never|must not|mustn't|do not|don't|under no circumstances|you will not)\b", re.I)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n\s*[-*\d.]+\s+|\n{2,}|\n", text)
    return [p.strip(" -*\t") for p in parts if len(p.strip()) > 3]


def keywords(sentence: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z][a-z'-]+", sentence.lower())
        if w not in STOP and len(w) > 3 and not w.endswith("'t")
    }


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def review(text: str, max_tokens: int = 2500, has_tools: bool | None = None) -> dict:
    findings: list[dict] = []

    def add(sev: str, code: str, msg: str, evidence: str = "") -> None:
        findings.append({"severity": sev, "code": code, "message": msg, "evidence": evidence[:160]})

    sents = sentences(text)
    tokens = estimate_tokens(text)
    words = len(re.findall(r"\S+", text))

    if tokens > max_tokens * 2:
        add(
            "high",
            "too-long",
            f"about {tokens} tokens (limit {max_tokens}); move reference data to retrieval",
        )
    elif tokens > max_tokens:
        add("medium", "long", f"about {tokens} tokens (limit {max_tokens}); trim or move detail out")

    # Contradictions: a positive and a negative rule about the same subject.
    pos = [(s, keywords(s)) for s in sents if POS_RE.search(s) and not NEG_RE.search(s)]
    neg = [(s, keywords(s)) for s in sents if NEG_RE.search(s)]
    reported = 0
    for ps, pk in pos:
        for ns, nk in neg:
            shared = pk & nk
            if len(shared) >= 2 and len(shared) / max(1, min(len(pk), len(nk))) >= 0.34:
                add(
                    "high",
                    "contradiction",
                    f"possible conflicting rules about: {', '.join(sorted(shared)[:4])}",
                    f"'{ps}' vs '{ns}'",
                )
                reported += 1
                if reported >= 10:
                    break
        if reported >= 10:
            break

    if not REFUSAL_RE.search(text):
        add(
            "high",
            "no-refusal-rule",
            "no rule for out-of-scope or disallowed requests (what to decline and how)",
        )
    if not HANDOVER_RE.search(text):
        add("high", "no-handover-rule", "no handover/escalation rule (when to pass to a human and how)")
    if not FORMAT_RE.search(text):
        add("low", "no-format", "no guidance on answer format, length or tone")
    mentions_tools = bool(TOOL_MENTION_RE.search(text)) if has_tools is None else has_tools
    if mentions_tools and not TOOL_RULE_RE.search(text):
        add("medium", "no-tool-rules", "tools are mentioned but there are no rules for when to call them")

    holders = [m.group(0) for m in PLACEHOLDER_RE.finditer(text)]
    if holders:
        uniq = list(dict.fromkeys(holders))
        add("high", "placeholder", f"{len(holders)} unfilled template placeholder(s)", ", ".join(uniq[:5]))
    for m in DATE_RE.finditer(text):
        add("medium", "hardcoded-date", "hard-coded date goes stale; inject it at request time", m.group(0))
    for m in SECRET_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        add(
            "high",
            "secret",
            "looks like a credential; never put secrets in a prompt",
            f"line {line} (value hidden)",
        )

    norm = Counter(re.sub(r"\W+", " ", s.lower()).strip() for s in sents if len(s) > 25)
    for s, n in norm.items():
        if n > 1:
            add("low", "duplicate", f"sentence repeated {n} times", s)
    vague = VAGUE_RE.findall(text)
    if vague:
        uniq = sorted({v.lower() for v in vague})
        add("low", "vague", f"{len(vague)} vague phrase(s); replace with concrete rules", ", ".join(uniq[:6]))
    caps = re.findall(r"\b[A-Z]{4,}\b", text)
    caps = [
        c for c in caps if c not in {"JSON", "HTML", "HTTP", "HTTPS", "UUID", "ISO", "TODO", "YAML", "SKU"}
    ]
    if len(caps) > 5:
        add("low", "shouting", f"{len(caps)} all-caps words; emphasis loses meaning when overused")

    return {
        "stats": {
            "characters": len(text),
            "words": words,
            "estimated_tokens": tokens,
            "sentences": len(sents),
        },
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Review a system prompt for contradictions and missing rules.")
    p.add_argument("file", help="prompt text file, or '-' for stdin")
    p.add_argument("--max-tokens", type=int, default=2500, help="estimated token budget (default 2500)")
    p.add_argument(
        "--tools", choices=["auto", "yes", "no"], default="auto", help="does the agent have tools?"
    )
    p.add_argument("--fail-on", choices=SEVERITIES, default="high", help="lowest severity that exits 1")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    has_tools = {"auto": None, "yes": True, "no": False}[args.tools]
    result = review(text, args.max_tokens, has_tools)
    findings = result["findings"]
    findings.sort(key=lambda x: -SEVERITIES.index(x["severity"]))
    failing = [x for x in findings if SEVERITIES.index(x["severity"]) >= SEVERITIES.index(args.fail_on)]
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        st = result["stats"]
        print(f"{st['words']} words, ~{st['estimated_tokens']} tokens, {st['sentences']} sentences")
        for x in findings:
            ev = f"\n          {x['evidence']}" if x["evidence"] else ""
            print(f"[{x['severity'].upper():6}] {x['message']} ({x['code']}){ev}")
        print(f"\n{len(findings)} finding(s), {len(failing)} at or above {args.fail_on}")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
