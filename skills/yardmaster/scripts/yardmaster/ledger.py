"""Spend report per harness and model. Pure arithmetic over normalised chats: no model call, no chat text."""

from .model import Chat
from .pricing import Pricing

CENT = 0.01  # 1 Copilot credit = $0.01 (as in the owner's reference script)


def _entry() -> dict:
    return {"credits": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_cached": 0, "est_usd": 0.0}


def ledger(chats: list[Chat], pricing: Pricing) -> dict:
    per: dict[str, dict] = {}
    unpriced: set[str] = set()
    for c in chats:
        h = per.setdefault(
            c.harness, {"chats": 0, "requests": 0, "credits": 0.0, "tokens_in": 0, "tokens_out": 0,
                        "tokens_cached": 0, "est_usd": 0.0, "models": {}}
        )
        h["chats"] += 1
        h["requests"] += c.requests
        if c.credits is not None:
            h["credits"] += c.credits
            h["est_usd"] += c.credits * CENT
            for m, v in c.models.items():
                if v:
                    e = h["models"].setdefault(_canon(pricing, c.harness, m), _entry())
                    e["credits"] += v
                    e["est_usd"] += v * CENT
        for t in c.turns:
            if t.role != "assistant" or not (t.tokens_in or t.tokens_out or t.tokens_cached):
                continue
            info = pricing.get(c.harness, t.model) if t.model else None
            e = h["models"].setdefault(info.id if info else (t.model or "?"), _entry())
            for k, v in (("tokens_in", t.tokens_in), ("tokens_out", t.tokens_out), ("tokens_cached", t.tokens_cached)):
                h[k] += v
                e[k] += v
            if info is not None and info.input is not None:
                cost = info.unit_cost(t.tokens_in, t.tokens_out, t.tokens_cached)
                h["est_usd"] += cost
                e["est_usd"] += cost
            elif info is None and c.credits is None and t.model:
                unpriced.add(f"{c.harness}:{t.model}")
    return {
        "harnesses": per,
        "total_est_usd": sum(h["est_usd"] for h in per.values()),
        "unpriced_models": sorted(unpriced),
    }


def _canon(pricing: Pricing, harness: str, model: str) -> str:
    info = pricing.get(harness, model)
    return info.id if info else model


def render_ledger(report: dict) -> str:
    if not report["harnesses"]:
        return "# Spend ledger\n\nNo chats in this range.\n"
    out = ["# Spend ledger", "", "| Harness | Chats | Requests | Credits | Tokens in | Tokens out | Cached | Est. USD |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, h in sorted(report["harnesses"].items()):
        out.append(f"| {name} | {h['chats']} | {h['requests']} | {h['credits']:,.2f} | {h['tokens_in']:,} | "
                   f"{h['tokens_out']:,} | {h['tokens_cached']:,} | ${h['est_usd']:,.2f} |")
    out += ["", f"**Total (estimated): ${report['total_est_usd']:,.2f}**", "", "## By model", "",
            "| Harness | Model | Credits | Tokens out | Est. USD |", "|---|---|---:|---:|---:|"]
    for name, h in sorted(report["harnesses"].items()):
        for m, e in sorted(h["models"].items(), key=lambda kv: -kv[1]["est_usd"]):
            out.append(f"| {name} | {m} | {e['credits']:,.2f} | {e['tokens_out']:,} | ${e['est_usd']:,.2f} |")
    if report["unpriced_models"]:
        out += ["", "Not priced (unknown to pricing.json): " + ", ".join(report["unpriced_models"])]
    return "\n".join(out) + "\n"
