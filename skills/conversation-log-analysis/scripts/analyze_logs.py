#!/usr/bin/env python3
"""Summarise chatbot / agent conversation logs: intents, failure turns, handovers.

Input JSONL in either shape (mixed is fine):
  message rows:      {"conversation_id": "c1", "role": "user", "content": "...",
                      "timestamp": "...", "intent": "refund", "event": "handover"}
  conversation rows: {"id": "c1", "messages": [{"role": "user", "content": "..."}, ...],
                      "intent": "refund", "resolved": true}
Roles: user, assistant (or bot/agent/ai), human (or human_agent/operator), tool, system.

Intents come from an "intent" field, or from --intents RULES.json
({"refund": ["refund", "money back"], ...}; first match on user messages wins).

A turn is flagged as a failure when the assistant: says it cannot help or did
not understand, apologises without an answer, errors in a tool call; or when
the user repeats themselves, asks for a human, or shows frustration.
A conversation is handed over when an event/role marks it, or the assistant
says it is transferring. "Abandoned" = last message is from the user.

Snippets are truncated and emails/phone numbers masked.

Exit codes: 0 = ok, 1 = --max-handover-rate or --max-failure-rate exceeded, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ASSISTANT_ROLES = {"assistant", "bot", "agent", "ai", "model"}
HUMAN_ROLES = {"human", "human_agent", "operator", "staff", "support_agent"}
FAIL_ASSISTANT_RE = re.compile(
    r"(i (?:can(?:no|')t|am (?:not able|unable)) (?:help|assist|answer|find|do that)|"
    r"i(?:'m| am) not sure (?:what|how|i understand)|i (?:don't|do not) (?:understand|know|have (?:that|"
    r"access|information))|could you (?:rephrase|clarify)|something went wrong|an error occurred|"
    r"i couldn(?:')?t find|outside (?:of )?my (?:scope|knowledge))",
    re.I,
)
FAIL_USER_RE = re.compile(
    r"(\b(?:talk|speak|chat) to (?:a |an )?(?:human|person|agent|someone|representative)\b|"
    r"\breal (?:person|human)\b|\bthat(?:'s| is) (?:not|wrong)\b|\bnot what i asked\b|\byou(?:'re| are) "
    r"(?:useless|not helping|wrong)\b|\bthis is (?:useless|ridiculous)\b|\bnot helpful\b|"
    r"\bi already (?:said|told)\b|\bwtf\b|\?{3,}|!{3,})",
    re.I,
)
HANDOVER_TEXT_RE = re.compile(
    r"(transfer(?:ring)? you|connect(?:ing)? you (?:with|to) (?:a|an|our) (?:human|agent|colleague|team)|"
    r"hand(?:ing)? (?:you )?over|escalat(?:e|ed|ing) (?:this|your)|a (?:human|team member|colleague) will "
    r"(?:reply|contact|be with))",
    re.I,
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d ().-]{7,}\d")


def clean(text: str, n: int = 100) -> str:
    text = PHONE_RE.sub("[PHONE]", EMAIL_RE.sub("[EMAIL]", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def role_of(msg: dict) -> str:
    r = str(msg.get("role") or msg.get("sender") or "").lower()
    if r in ASSISTANT_ROLES:
        return "assistant"
    if r in HUMAN_ROLES:
        return "human"
    return r or "unknown"


def content_of(msg: dict) -> str:
    c = msg.get("content", msg.get("text", ""))
    if isinstance(c, list):
        return " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c or "")


def load(paths: list[Path]) -> dict[str, dict]:
    convs: dict[str, dict] = {}
    for path in paths:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{n}: invalid JSON") from exc
            if "messages" in row:
                cid = str(row.get("id") or row.get("conversation_id") or f"{path.name}:{n}")
                conv = convs.setdefault(cid, {"messages": [], "meta": {}})
                conv["messages"] += row["messages"]
                conv["meta"].update({k: v for k, v in row.items() if k != "messages"})
            else:
                cid = str(row.get("conversation_id") or row.get("session_id") or "unknown")
                conv = convs.setdefault(cid, {"messages": [], "meta": {}})
                conv["messages"].append(row)
                if row.get("intent") and "intent" not in conv["meta"]:
                    conv["meta"]["intent"] = row["intent"]
    for conv in convs.values():
        if all("timestamp" in m for m in conv["messages"]):
            conv["messages"].sort(key=lambda m: str(m["timestamp"]))
    return convs


def classify_intent(conv: dict, rules: dict[str, list[str]]) -> str:
    if conv["meta"].get("intent"):
        return str(conv["meta"]["intent"])
    users = " ".join(content_of(m) for m in conv["messages"] if role_of(m) == "user").lower()
    for intent, words in rules.items():
        if any(w.lower() in users for w in words):
            return intent
    return "unclassified"


def analyse(convs: dict[str, dict], rules: dict[str, list[str]], examples: int = 5) -> dict:
    intents = Counter()
    per_intent = defaultdict(lambda: {"conversations": 0, "handover": 0, "failure_turns": 0, "abandoned": 0})
    failure_reasons = Counter()
    failure_examples = []
    handovers = abandoned = with_failure = tool_errors = 0
    turns_total = 0
    lengths = []
    for cid, conv in convs.items():
        msgs = conv["messages"]
        intent = classify_intent(conv, rules)
        intents[intent] += 1
        pi = per_intent[intent]
        pi["conversations"] += 1
        user_turns = [m for m in msgs if role_of(m) == "user"]
        turns_total += len(user_turns)
        lengths.append(len(user_turns))
        handed = bool(conv["meta"].get("handover")) or conv["meta"].get("resolved_by") == "human"
        conv_fail = 0
        prev_user = ""
        for i, m in enumerate(msgs):
            role, text = role_of(m), content_of(m)
            event = str(m.get("event", "")).lower()
            reason = None
            if event in ("handover", "escalation", "transfer") or role == "human":
                handed = True
            if role == "assistant":
                if HANDOVER_TEXT_RE.search(text):
                    handed = True
                if FAIL_ASSISTANT_RE.search(text):
                    reason = "assistant_could_not_help"
            elif role == "tool" and (
                m.get("error") or re.search(r"\b(error|exception|timed? ?out)\b", text, re.I)
            ):
                tool_errors += 1
                reason = "tool_error"
            elif role == "user":
                if FAIL_USER_RE.search(text):
                    reason = "user_frustrated_or_asked_for_human"
                elif prev_user and SequenceMatcher(None, prev_user.lower(), text.lower()).ratio() > 0.8:
                    reason = "user_repeated"
                prev_user = text
            if reason:
                conv_fail += 1
                failure_reasons[reason] += 1
                if len(failure_examples) < examples:
                    failure_examples.append(
                        {"conversation": cid, "turn": i, "reason": reason, "text": clean(text)}
                    )
        if msgs and role_of(msgs[-1]) == "user":
            abandoned += 1
            pi["abandoned"] += 1
        if handed:
            handovers += 1
            pi["handover"] += 1
        if conv_fail:
            with_failure += 1
        pi["failure_turns"] += conv_fail
    n = len(convs)
    lengths.sort()
    return {
        "conversations": n,
        "user_turns": turns_total,
        "turns_per_conversation": {
            "mean": round(turns_total / n, 2) if n else 0,
            "median": lengths[len(lengths) // 2] if lengths else 0,
            "max": lengths[-1] if lengths else 0,
        },
        "handover_rate": round(handovers / n, 4) if n else 0,
        "failure_conversation_rate": round(with_failure / n, 4) if n else 0,
        "abandon_rate": round(abandoned / n, 4) if n else 0,
        "tool_errors": tool_errors,
        "failure_reasons": dict(failure_reasons.most_common()),
        "intents": [
            {
                "intent": k,
                "conversations": v,
                "share": round(v / n, 4),
                "handover_rate": round(per_intent[k]["handover"] / v, 4),
                "failure_turns": per_intent[k]["failure_turns"],
                "abandoned": per_intent[k]["abandoned"],
            }
            for k, v in intents.most_common()
        ],
        "failure_examples": failure_examples,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Summarise chat logs: intents, failure turns, handover rate.")
    p.add_argument("files", nargs="+", type=Path, help="JSONL log files")
    p.add_argument("--intents", type=Path, help='JSON {"intent": ["keyword", ...]} rules')
    p.add_argument("--examples", type=int, default=5, help="failure examples to show (default 5)")
    p.add_argument("--max-handover-rate", type=float, help="exit 1 if handover rate (0-1) is higher")
    p.add_argument("--max-failure-rate", type=float, help="exit 1 if failure conversation rate is higher")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        rules = json.loads(args.intents.read_text(encoding="utf-8")) if args.intents else {}
        convs = load(args.files)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rep = analyse(convs, rules, args.examples)
    if args.json:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        t = rep["turns_per_conversation"]
        print(
            f"{rep['conversations']} conversations, {rep['user_turns']} user turns "
            f"(mean {t['mean']}, median {t['median']}, max {t['max']})"
        )
        print(
            f"handover rate {rep['handover_rate']:.1%}, conversations with a failure turn "
            f"{rep['failure_conversation_rate']:.1%}, abandoned {rep['abandon_rate']:.1%}, "
            f"tool errors {rep['tool_errors']}"
        )
        print("\nIntent                     convs  share  handover  fail-turns")
        for i in rep["intents"]:
            print(
                f"{i['intent'][:26]:26} {i['conversations']:5}  {i['share']:5.0%}  "
                f"{i['handover_rate']:8.0%}  "
                f"{i['failure_turns']:10}"
            )
        if rep["failure_reasons"]:
            print("\nFailure reasons: " + ", ".join(f"{k} {v}" for k, v in rep["failure_reasons"].items()))
        for ex in rep["failure_examples"]:
            print(f"  {ex['conversation']} turn {ex['turn']} [{ex['reason']}]: {ex['text']}")
    bad = (args.max_handover_rate is not None and rep["handover_rate"] > args.max_handover_rate) or (
        args.max_failure_rate is not None and rep["failure_conversation_rate"] > args.max_failure_rate
    )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
