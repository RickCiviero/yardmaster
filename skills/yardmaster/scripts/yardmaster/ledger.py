"""Usage report per harness, model and strength tier: requests, tokens and Copilot credits. Pure arithmetic over normalised
chats: no model call, no chat text.

The headline is fresh tokens, input plus output. Cache reads are shown apart, because they are cheap to read and would
otherwise swamp the total. A Copilot credit is a usage unit that Copilot itself reports; this report never converts it."""

from .catalog import TIERS, Catalog
from .model import Chat

UNKNOWN = "unknown"


def _entry(tier: str) -> dict:
    return {"tier": tier, "credits": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_cached": 0}


def _model(catalog: Catalog, harness: str, name: str) -> tuple[str, str]:
    info = catalog.get(harness, name)
    return (info.id, info.tier) if info else (name, UNKNOWN)


def ledger(chats: list[Chat], catalog: Catalog) -> dict:
    per: dict[str, dict] = {}
    for c in chats:
        h = per.setdefault(c.harness, {"chats": 0, "requests": 0, "credits": 0.0, "tokens_in": 0, "tokens_out": 0,
                                       "tokens_cached": 0, "models": {}})
        h["chats"] += 1
        h["requests"] += c.requests
        if c.credits is not None:
            h["credits"] += c.credits
            for m, v in c.models.items():
                if v:
                    name, tier = _model(catalog, c.harness, m)
                    h["models"].setdefault(name, _entry(tier))["credits"] += v
        for t in c.turns:
            if t.role != "assistant" or not (t.tokens_in or t.tokens_out or t.tokens_cached):
                continue
            name, tier = _model(catalog, c.harness, t.model or "?")
            e = h["models"].setdefault(name, _entry(tier))
            for k, v in (("tokens_in", t.tokens_in), ("tokens_out", t.tokens_out), ("tokens_cached", t.tokens_cached)):
                h[k] += v
                e[k] += v
    by_tier = {tier: 0 for tier in (*TIERS, UNKNOWN)}
    for h in per.values():
        for e in h["models"].values():
            by_tier[e["tier"]] += e["tokens_in"] + e["tokens_out"]
    return {
        "harnesses": per,
        "fresh_tokens": sum(h["tokens_in"] + h["tokens_out"] for h in per.values()),
        "by_tier": by_tier,
    }


def render_ledger(report: dict) -> str:
    if not report["harnesses"]:
        return "# Usage ledger\n\nNo chats in this range.\n"
    out = ["# Usage ledger", "", "| Harness | Chats | Requests | Credits | Tokens in | Tokens out | Cache reads |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for name, h in sorted(report["harnesses"].items()):
        out.append(f"| {name} | {h['chats']} | {h['requests']} | {h['credits']:,.2f} | {h['tokens_in']:,} | "
                   f"{h['tokens_out']:,} | {h['tokens_cached']:,} |")
    fresh = report["fresh_tokens"]
    out += ["", f"**Fresh tokens (input + output): {fresh:,}.** Cache reads are not counted.", "",
            "## By strength", "", "| Tier | Fresh tokens | Share |", "|---|---:|---:|"]
    for tier, n in report["by_tier"].items():
        if n or tier != UNKNOWN:
            out.append(f"| {tier} | {n:,} | {f'{n / fresh:.0%}' if fresh else '-'} |")
    out += ["", "## By model", "", "| Harness | Model | Tier | Credits | Tokens in | Tokens out | Cache reads |",
            "|---|---|---|---:|---:|---:|---:|"]
    for name, h in sorted(report["harnesses"].items()):
        for m, e in sorted(h["models"].items(), key=lambda kv: -(kv[1]["tokens_in"] + kv[1]["tokens_out"])):
            out.append(f"| {name} | {m} | {e['tier']} | {e['credits']:,.2f} | {e['tokens_in']:,} | "
                       f"{e['tokens_out']:,} | {e['tokens_cached']:,} |")
    if report["by_tier"][UNKNOWN]:
        out += ["", "Some models are not in the catalog (models.json), so their tier is unknown."]
    return "\n".join(out) + "\n"
