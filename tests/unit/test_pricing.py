import json
from pathlib import Path

import pytest
from yardmaster.pricing import TIERS, ModelInfo, Pricing, load_pricing

SHIPPED = Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "pricing.json"


def _doc(models, unit="usd_per_mtok", harness="h"):
    return {"schema": 1, "as_of": "2026-11-23", "verified": False, "harnesses": {harness: {"unit": unit, "models": models}}}


def _m(id_, tier, out=1.0, **kw):
    return {"id": id_, "aliases": kw.pop("aliases", []), "tier": tier, "input": out / 5, "output": out, "cached": out / 50,
            "multiplier": None, "notes": [], **kw}


def _write(tmp_path, doc, name="pricing.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return p


def test_tiers_are_ordered():
    assert TIERS == ("light", "standard", "heavy", "frontier")


def test_shipped_pricing_loads_and_covers_v1_harnesses():
    p = load_pricing(SHIPPED)
    for h in ("vscode-copilot", "copilot-cli", "claude-code", "codex"):
        tiers = {m.tier for m in p.models(h)}
        assert {"light", "standard", "heavy"} <= tiers, h
    assert p.as_of and p.verified is False  # estimated until the owner verifies against vendor pages


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["harnesses"]["h"]["models"][0].update(tier="giga"),
        lambda d: d["harnesses"]["h"]["models"].append(_m("a", "light")),  # duplicate id
        lambda d: d["harnesses"]["h"]["models"].append(_m("b", "light", aliases=["a"])),  # alias collides with id
        lambda d: d["harnesses"]["h"]["models"][0].update(output=-1),
        lambda d: d["harnesses"]["h"]["models"][0].update(output=float("nan")),
        lambda d: d.update(schema=2),
        lambda d: d["harnesses"]["h"].update(unit="euros"),
        lambda d: d["harnesses"].update(h="nope"),
    ],
)
def test_pricing_schema_rejects_bad_input(tmp_path, mutate):
    doc = _doc([_m("a", "light")])
    mutate(doc)
    with pytest.raises(ValueError):
        load_pricing(_write(tmp_path, doc))


def test_credit_unit_needs_multiplier(tmp_path):
    doc = _doc([{"id": "a", "aliases": [], "tier": "light", "multiplier": None, "notes": []}], unit="credit")
    with pytest.raises(ValueError):
        load_pricing(_write(tmp_path, doc))


def test_get_resolves_id_alias_and_copilot_prefix(tmp_path):
    p = load_pricing(_write(tmp_path, _doc([_m("opus", "heavy", aliases=["claude-opus-5-5"])])))
    assert p.get("h", "opus").id == p.get("h", "claude-opus-5-5").id == p.get("h", "copilot/claude-opus-5-5").id == "opus"
    assert p.get("h", "nope") is None and p.get("other", "opus") is None
    assert p.tier_of("h", "claude-opus-5-5") == "heavy" and p.tier_of("h", "nope") is None


def test_cheapest_with_deny_and_fallback_up(tmp_path):
    p = load_pricing(_write(tmp_path, _doc([
        _m("l1", "light", 2.0), _m("l2", "light", 1.0), _m("s1", "standard", 5.0), _m("f1", "frontier", 50.0)])))
    assert p.cheapest("h", "light", frozenset()).id == "l2"
    assert p.cheapest("h", "light", frozenset({"l2"})).id == "l1"
    assert p.cheapest("h", "light", frozenset({"l1", "l2"})).id == "s1"  # no light left: go UP, never down
    assert p.cheapest("h", "heavy", frozenset()).id == "f1"  # nothing heavy: next tier up
    assert p.cheapest("h", "frontier", frozenset({"f1"})) is None
    assert p.cheapest("h", "standard", frozenset({"s1"})).id == "f1"


def test_cheapest_orders_credit_models_by_multiplier(tmp_path):
    doc = _doc([{"id": "a", "aliases": [], "tier": "light", "multiplier": 0.33, "notes": []},
                {"id": "b", "aliases": [], "tier": "light", "multiplier": 0.0, "notes": []}], unit="credit")
    assert load_pricing(_write(tmp_path, doc)).cheapest("h", "light", frozenset()).id == "b"


def test_unit_cost(tmp_path):
    p = load_pricing(_write(tmp_path, _doc([_m("a", "light", 10.0)])))
    m = p.get("h", "a")
    assert isinstance(m, ModelInfo)
    assert m.unit_cost(1_000_000, 1_000_000, 1_000_000) == pytest.approx(2.0 + 10.0 + 0.2)
    assert m.unit_cost(0, 0, 0) == 0


def test_local_override_changes_prices_but_cannot_add_models_or_tiers(tmp_path):
    base = _write(tmp_path, _doc([_m("a", "light", 1.0)]))
    local = _write(tmp_path, {"harnesses": {"h": {"models": [
        {"id": "a", "output": 9.0, "tier": "frontier"}, {"id": "evil", "tier": "light", "output": 0.0}]}}}, "local.json")
    p = load_pricing(base, local)
    assert [m.id for m in p.models("h")] == ["a"]
    assert p.get("h", "a").output == 9.0 and p.get("h", "a").tier == "light"


def test_models_unknown_harness_empty():
    assert isinstance(load_pricing(SHIPPED), Pricing) and load_pricing(SHIPPED).models("nope") == []
