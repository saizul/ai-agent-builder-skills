#!/usr/bin/env python3
"""Redact personal data from text, chat logs or JSONL before it reaches an LLM or a log store.

Detects: email addresses, phone numbers (international and common national
formats), payment card numbers (Luhn-checked), IBANs (mod-97 checked),
US social security numbers, IPv4 addresses, and credential-like strings
(key=value secrets, bearer tokens). Extra patterns can be added with
--pattern NAME=REGEX.

Modes: --mode label (default, "[EMAIL]"), mask ("j***@e***.com" style),
hash (stable "[EMAIL:1a2b3c4d]" so the same value maps to the same token;
use --salt to make hashes unguessable).

With --jsonl, only string values inside each JSON object are redacted
(keys and structure are kept). --check prints counts only and exits 1 if
anything was found (use it as a CI or pre-ingestion gate). Values found are
never printed.

Exit codes: 0 = ok (or nothing found with --check), 1 = PII found with --check, 2 = error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (
        "SECRET",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|passwd|pwd|access[_-]?token|auth[_-]?token)\b"
            r"\s*[:=]\s*[\"']?[^\s\"',;]{6,}"
        ),
    ),
    ("SECRET", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){12,18}\d\b")),
    ("SSN", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    ("IPV4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    (
        "PHONE",
        re.compile(
            r"(?<![\w+])(?:\+\d{1,3}[ .-]?)?(?:\(\d{1,4}\)[ .-]?)?\d{2,4}(?:[ .-]\d{2,4}){1,4}(?![\w-])"
        ),
    ),
]


def luhn_ok(number: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def iban_ok(value: str) -> bool:
    s = value.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    s = s[4:] + s[:4]
    num = "".join(str(int(c, 36)) for c in s)
    return int(num) % 97 == 1


def phone_ok(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if not 8 <= len(digits) <= 15:
        return False
    # Avoid dates, versions and plain numbers: need a + or at least two separators.
    if value.startswith("+") or value.startswith("("):
        return True
    return len(re.findall(r"[ .-]", value)) >= 2 and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)


VALIDATORS = {"CARD": luhn_ok, "IBAN": iban_ok, "PHONE": phone_ok}


def mask(value: str) -> str:
    if "@" in value:
        user, _, domain = value.partition("@")
        dom, _, tld = domain.rpartition(".")
        return f"{user[:1]}***@{dom[:1]}***.{tld}"
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 8:
        return "*" * (len(digits) - 4) + digits[-4:]
    return value[:1] + "***"


class Redactor:
    def __init__(
        self,
        mode: str = "label",
        salt: str = "",
        extra: list[tuple[str, str]] | None = None,
        kinds: set[str] | None = None,
    ) -> None:
        self.mode = mode
        self.salt = salt
        self.counts: Counter = Counter()
        self.patterns = [(n, re.compile(rx)) for n, rx in extra or []] + PATTERNS
        if kinds:
            self.patterns = [(n, rx) for n, rx in self.patterns if n in kinds]

    def _replacement(self, kind: str, value: str) -> str:
        if self.mode == "mask":
            return f"[{kind}]" if kind == "SECRET" else mask(value)
        if self.mode == "hash":
            digest = hashlib.sha256((self.salt + value).encode()).hexdigest()[:8]
            return f"[{kind}:{digest}]"
        return f"[{kind}]"

    def redact(self, text: str) -> str:
        for kind, rx in self.patterns:
            check = VALIDATORS.get(kind)

            def repl(m: re.Match, kind=kind, check=check) -> str:
                value = m.group(0)
                if value.startswith("[") or (check and not check(value)):
                    return value
                self.counts[kind] += 1
                return self._replacement(kind, value)

            text = rx.sub(repl, text)
        return text

    def redact_obj(self, obj):
        if isinstance(obj, str):
            return self.redact(obj)
        if isinstance(obj, list):
            return [self.redact_obj(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.redact_obj(v) for k, v in obj.items()}
        return obj


def parse_pattern(text: str) -> tuple[str, str]:
    name, sep, rx = text.partition("=")
    if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        raise argparse.ArgumentTypeError("use NAME=REGEX with an upper-case NAME, e.g. ORDER=ORD-\\d{6}")
    try:
        re.compile(rx)
    except re.error as exc:
        raise argparse.ArgumentTypeError(f"bad regex: {exc}") from exc
    return name, rx


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Redact PII and secrets from text or JSONL.")
    p.add_argument("file", help="input file, or '-' for stdin")
    p.add_argument("--mode", choices=["label", "mask", "hash"], default="label")
    p.add_argument("--salt", default="", help="salt for --mode hash (keep it private)")
    p.add_argument("--jsonl", action="store_true", help="input is JSONL; redact string values only")
    p.add_argument("--only", help="comma-separated kinds to detect, e.g. EMAIL,PHONE")
    p.add_argument("--pattern", action="append", type=parse_pattern, default=[], help="extra NAME=REGEX")
    p.add_argument("--out", type=Path, help="write redacted output here instead of stdout")
    p.add_argument("--check", action="store_true", help="report counts only; exit 1 if anything found")
    p.add_argument(
        "--json", action="store_true", help="print the counts report as JSON (stderr unless --check)"
    )
    args = p.parse_args(argv)
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    kinds = {k.strip().upper() for k in args.only.split(",")} if args.only else None
    r = Redactor(args.mode, args.salt, args.pattern, kinds)
    if args.jsonl:
        out_lines = []
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                out_lines.append(json.dumps(r.redact_obj(json.loads(line)), ensure_ascii=False))
            except json.JSONDecodeError:
                print(f"error: line {n} is not JSON", file=sys.stderr)
                return 2
        result = "\n".join(out_lines) + "\n"
    else:
        result = r.redact(text)
    report = {"total": sum(r.counts.values()), "by_kind": dict(sorted(r.counts.items()))}
    if args.check:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            kinds_txt = ", ".join(f"{k} {v}" for k, v in report["by_kind"].items()) or "none"
            print(f"PII/secrets found: {report['total']} ({kinds_txt})")
        return 1 if report["total"] else 0
    if args.out:
        args.out.write_text(result, encoding="utf-8")
    else:
        sys.stdout.write(result)
    stream = sys.stdout if args.out else sys.stderr
    if args.json:
        print(json.dumps(report), file=stream)
    elif args.out:
        print(f"redacted {report['total']} value(s) -> {args.out}", file=stream)
    return 0


if __name__ == "__main__":
    sys.exit(main())
