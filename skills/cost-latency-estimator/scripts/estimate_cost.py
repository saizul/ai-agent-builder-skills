#!/usr/bin/env python3
"""Estimate tokens, monthly LLM cost and per-turn latency from traffic assumptions.

Nothing about any LLM provider is built in: prices and speeds come from the
"models" table in your config file. Copy assets/example-config.json, replace
the placeholder prices with your LLM provider's current published prices,
and adjust traffic and token assumptions.

Model per turn:
  input  = static (system prompt + tool definitions) + user message
           + retrieved context + history (previous turns, if carried over)
  output = answer tokens
  each tool call adds one more model call (input grows by the tool result,
  output = tool_call_tokens) plus tool latency.
  cached_fraction of the static part is billed at cached_input_per_mtok.

--set path=value overrides any config value (e.g. traffic.conversations_per_day=5000).
--compare adds a 0.5x / 1x / 2x / 5x traffic table. --tokens-file estimates
the token count of a prompt or document (characters / 4) to fill the config.

Exit codes: 0 = ok, 1 = estimate exceeds budget_monthly, 2 = config error.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

DEFAULTS = {
    "currency": "USD",
    "traffic": {"conversations_per_day": 100, "days_per_month": 30, "turns_per_conversation": 3},
    "tokens": {
        "system_prompt": 800,
        "tool_definitions": 0,
        "user_message": 50,
        "retrieved_context": 0,
        "output": 200,
        "history_carryover": True,
        "tool_calls_per_turn": 0,
        "tool_result": 300,
        "tool_call_tokens": 60,
    },
    "caching": {"cached_fraction_of_static": 0.0},
    "latency": {"tool_latency_ms": 300, "overhead_ms": 150},
    "extra_monthly": {},
}
REQUIRED_MODEL_KEYS = ("input_per_mtok", "output_per_mtok")


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def set_path(cfg: dict, assignment: str) -> None:
    path, sep, raw = assignment.partition("=")
    if not sep:
        raise ValueError(f"--set needs path=value, got {assignment!r}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    cur = cfg
    parts = path.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def validate(cfg: dict) -> list[str]:
    errors = []
    models = cfg.get("models")
    if not isinstance(models, dict) or not models:
        return ["config needs a 'models' table with your LLM provider's prices"]
    for name, m in models.items():
        for key in REQUIRED_MODEL_KEYS:
            if not isinstance(m.get(key), (int, float)) or m[key] < 0:
                errors.append(f"models.{name}.{key} must be a non-negative number (price per 1M tokens)")
    routing = cfg.get("routing") or {next(iter(models)): 1.0}
    cfg["routing"] = routing
    for name in routing:
        if name not in models:
            errors.append(f"routing refers to unknown model '{name}'")
    total = sum(routing.values())
    if abs(total - 1.0) > 0.001:
        errors.append(f"routing shares must add up to 1.0 (got {total:g})")
    cf = cfg["caching"].get("cached_fraction_of_static", 0)
    if not 0 <= cf <= 1:
        errors.append("caching.cached_fraction_of_static must be between 0 and 1")
    for key in ("conversations_per_day", "days_per_month", "turns_per_conversation"):
        if not isinstance(cfg["traffic"].get(key), (int, float)) or cfg["traffic"][key] <= 0:
            errors.append(f"traffic.{key} must be a positive number")
    return errors


def per_conversation(cfg: dict, model: dict) -> dict:
    t = cfg["tokens"]
    turns = int(round(cfg["traffic"]["turns_per_conversation"]))
    static = t["system_prompt"] + t["tool_definitions"]
    cached_frac = cfg["caching"].get("cached_fraction_of_static", 0.0)
    tool_calls = t["tool_calls_per_turn"]
    totals = {"input_tokens": 0.0, "cached_input_tokens": 0.0, "output_tokens": 0.0, "model_calls": 0.0}
    latencies = []
    for k in range(1, turns + 1):
        history = (k - 1) * (t["user_message"] + t["output"]) if t["history_carryover"] else 0
        base_input = static + t["user_message"] + t["retrieved_context"] + history
        # Final answer call + tool_calls extra calls, each seeing the growing context.
        calls_input = base_input * (1 + tool_calls) + t["tool_result"] * tool_calls * (tool_calls + 1) / 2
        calls_cached = static * cached_frac * (1 + tool_calls)
        totals["input_tokens"] += calls_input - calls_cached
        totals["cached_input_tokens"] += calls_cached
        totals["output_tokens"] += t["output"] + t["tool_call_tokens"] * tool_calls
        totals["model_calls"] += 1 + tool_calls
        ttft = model.get("ttft_ms", 500)
        tps = model.get("output_tokens_per_sec", 50) or 50
        lat = (
            (1 + tool_calls) * ttft
            + (t["output"] + t["tool_call_tokens"] * tool_calls) / tps * 1000
            + tool_calls * cfg["latency"]["tool_latency_ms"]
            + cfg["latency"]["overhead_ms"]
        )
        latencies.append(lat)
    price_in = model["input_per_mtok"] / 1e6
    price_cached = model.get("cached_input_per_mtok", model["input_per_mtok"]) / 1e6
    price_out = model["output_per_mtok"] / 1e6
    cost = {
        "input": totals["input_tokens"] * price_in,
        "cached_input": totals["cached_input_tokens"] * price_cached,
        "output": totals["output_tokens"] * price_out,
    }
    return {
        **totals,
        "cost": cost,
        "cost_total": sum(cost.values()),
        "latency_first_turn_ms": latencies[0] if latencies else 0,
        "latency_last_turn_ms": latencies[-1] if latencies else 0,
        "latency_avg_turn_ms": sum(latencies) / len(latencies) if latencies else 0,
    }


def estimate(cfg: dict) -> dict:
    conv_month = cfg["traffic"]["conversations_per_day"] * cfg["traffic"]["days_per_month"]
    by_model = {}
    llm_month = 0.0
    tokens_month = {"input": 0.0, "cached_input": 0.0, "output": 0.0}
    for name, share in cfg["routing"].items():
        pc = per_conversation(cfg, cfg["models"][name])
        n = conv_month * share
        month = pc["cost_total"] * n
        llm_month += month
        tokens_month["input"] += pc["input_tokens"] * n
        tokens_month["cached_input"] += pc["cached_input_tokens"] * n
        tokens_month["output"] += pc["output_tokens"] * n
        by_model[name] = {
            "share": share,
            "conversations_per_month": round(n),
            "cost_per_conversation": round(pc["cost_total"], 6),
            "cost_per_month": round(month, 2),
            "tokens_per_conversation": {
                "input": round(pc["input_tokens"]),
                "cached_input": round(pc["cached_input_tokens"]),
                "output": round(pc["output_tokens"]),
            },
            "model_calls_per_conversation": pc["model_calls"],
            "latency_ms": {
                "first_turn": round(pc["latency_first_turn_ms"]),
                "avg_turn": round(pc["latency_avg_turn_ms"]),
                "last_turn": round(pc["latency_last_turn_ms"]),
            },
            "cost_split_per_conversation": {k: round(v, 6) for k, v in pc["cost"].items()},
        }
    extra = sum(float(v) for v in cfg.get("extra_monthly", {}).values())
    total = llm_month + extra
    return {
        "currency": cfg.get("currency", "USD"),
        "conversations_per_month": round(conv_month),
        "llm_cost_per_month": round(llm_month, 2),
        "extra_cost_per_month": round(extra, 2),
        "total_cost_per_month": round(total, 2),
        "cost_per_conversation": round(total / conv_month, 6) if conv_month else 0,
        "tokens_per_month": {k: round(v) for k, v in tokens_month.items()},
        "by_model": by_model,
        "budget_monthly": cfg.get("budget_monthly"),
        "over_budget": bool(cfg.get("budget_monthly") is not None and total > float(cfg["budget_monthly"])),
    }


def load_config(path: Path | None, sets: list[str]) -> dict:
    user = json.loads(path.read_text(encoding="utf-8")) if path else {}
    cfg = deep_merge(DEFAULTS, user)
    for s in sets:
        set_path(cfg, s)
    return cfg


def fmt_money(v: float, cur: str) -> str:
    return f"{v:,.2f} {cur}" if v >= 1 else f"{v:.4f} {cur}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Estimate LLM tokens, monthly cost and latency from a config.")
    p.add_argument("config", nargs="?", type=Path, help="JSON config (see assets/example-config.json)")
    p.add_argument("--set", action="append", default=[], metavar="PATH=VALUE", help="override a config value")
    p.add_argument("--compare", action="store_true", help="add a traffic multiplier table")
    p.add_argument(
        "--tokens-file", type=Path, action="append", help="estimate tokens of a text file (chars/4)"
    )
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)

    if args.tokens_file and not args.config:
        rows = []
        for f in args.tokens_file:
            text = f.read_text(encoding="utf-8", errors="replace")
            rows.append({"file": str(f), "characters": len(text), "estimated_tokens": (len(text) + 3) // 4})
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['file']}: {r['characters']} chars, ~{r['estimated_tokens']} tokens")
            print("Rough estimate (chars/4); use your LLM provider's tokenizer for exact counts.")
        return 0
    if not args.config:
        p.error("a config file is required (or use --tokens-file alone)")
    try:
        cfg = load_config(args.config, args.set)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = validate(cfg)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 2
    result = estimate(cfg)
    if args.compare:
        base = cfg["traffic"]["conversations_per_day"]
        result["traffic_scenarios"] = []
        for mult in (0.5, 1, 2, 5):
            c2 = copy.deepcopy(cfg)
            c2["traffic"]["conversations_per_day"] = base * mult
            r2 = estimate(c2)
            result["traffic_scenarios"].append(
                {
                    "multiplier": mult,
                    "conversations_per_day": base * mult,
                    "total_cost_per_month": r2["total_cost_per_month"],
                }
            )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        cur = result["currency"]
        print(f"Conversations/month: {result['conversations_per_month']:,}")
        for name, m in result["by_model"].items():
            tpc = m["tokens_per_conversation"]
            lat = m["latency_ms"]
            print(
                f"  {name} ({m['share']:.0%}): {fmt_money(m['cost_per_conversation'], cur)}/conversation, "
                f"{fmt_money(m['cost_per_month'], cur)}/month; tokens/conv in {tpc['input']:,} "
                f"cached {tpc['cached_input']:,} out {tpc['output']:,}; latency first/avg/last turn "
                f"{lat['first_turn']}/{lat['avg_turn']}/{lat['last_turn']} ms"
            )
        print(f"LLM cost/month:   {fmt_money(result['llm_cost_per_month'], cur)}")
        print(f"Other cost/month: {fmt_money(result['extra_cost_per_month'], cur)}")
        print(f"TOTAL/month:      {fmt_money(result['total_cost_per_month'], cur)}")
        if result.get("traffic_scenarios"):
            for s in result["traffic_scenarios"]:
                print(
                    f"  x{s['multiplier']:<4} {s['conversations_per_day']:>10,.0f}/day -> "
                    f"{fmt_money(s['total_cost_per_month'], cur)}"
                )
        if result["budget_monthly"] is not None:
            state = "OVER" if result["over_budget"] else "within"
            print(f"Budget {fmt_money(float(result['budget_monthly']), cur)}: {state} budget")
        print("Estimate only: verify prices with your LLM provider and measure real token counts.")
    return 1 if result["over_budget"] else 0


if __name__ == "__main__":
    sys.exit(main())
