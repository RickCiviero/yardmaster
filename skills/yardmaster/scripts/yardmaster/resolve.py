"""Turn the tier-based plan into one concrete model per group for a given harness."""

from dataclasses import dataclass

from .pricing import TIERS, ModelInfo, Pricing
from .schema import Plan, ValidationError


@dataclass(frozen=True)
class ResolvedGroup:
    name: str
    tier: str
    when: str
    examples: list[str]
    model: ModelInfo


def resolve_plan(plan: Plan, harness: str, pricing: Pricing, deny: frozenset[str]) -> list[ResolvedGroup]:
    denied = {d.lower() for d in deny}
    by_model: dict[str, list[tuple[object, ModelInfo]]] = {}
    for g in plan.groups:
        model = None
        if (pref := g.prefer.get(harness)) and (info := pricing.get(harness, pref)):
            if not ({info.id.lower(), *(a.lower() for a in info.aliases)} & denied):
                model = info
        model = model or pricing.cheapest(harness, g.tier, deny)
        if model is None:
            raise ValidationError(f"no model available for group {g.name!r} on {harness}")
        by_model.setdefault(model.id, []).append((g, model))

    out: list[ResolvedGroup] = []
    for members in by_model.values():
        groups = [g for g, _ in members]
        ordered = sorted(groups, key=lambda g: -TIERS.index(g.tier))  # highest tier first; plan order within a tier
        top = ordered[0]
        whens = [g.when.strip() for g in ordered]
        dot = "." if all(w.endswith(".") for w in whens) else ""
        examples = [e for g in ordered for e in g.examples][:3]
        out.append(ResolvedGroup(top.name, top.tier, "; ".join(w.rstrip(".") for w in whens) + dot, examples, members[0][1]))
    return sorted(out, key=lambda r: r.model.sort_key, reverse=True)
