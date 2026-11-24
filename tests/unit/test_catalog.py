"""The model catalog: which models each harness offers, how strong each one is, and that it holds no prices."""

import json
from pathlib import Path

import pytest
from yardmaster.catalog import TIERS, ModelInfo, default_catalog, load_catalog

SHIPPED = Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "scripts" / "yardmaster" / "models.json"


def _write(tmp_path, doc, name="models.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _doc(models, harness="h"):
    return {"schema": 2, "as_of": "2026-11-24", "harnesses": {harness: {"models": models}}}


def _m(mid, tier, aliases=()):
    return {"id": mid, "tier": tier, "aliases": list(aliases)}


def test_shipped_catalog_covers_every_harness_with_the_current_families():
    c = default_catalog()
    assert c.harnesses() == ["claude-code", "vscode-copilot", "copilot-cli", "codex"]
    assert c.get("claude-code", "claude-opus-5-5").id == "opus"  # a full model id is an alias of the family
    assert c.get("codex", "gpt-6.2-sol").tier == "heavy"
    assert c.get("vscode-copilot", "copilot/gpt-6-luna").id == "gpt-6-luna"
    for h in c.harnesses():
        assert {m.tier for m in c.models(h)} <= set(TIERS)


def test_the_catalog_holds_no_prices():
    raw = SHIPPED.read_text(encoding="utf-8").lower()
    assert not any(key in raw for key in ('"input"', '"output"', '"cached"', '"multiplier"', "usd", "$"))
    assert not {"input", "output", "cached", "multiplier", "sort_key"} & set(ModelInfo.__dataclass_fields__)


def test_choose_takes_the_weakest_listed_model_of_the_tier(tmp_path):
    c = load_catalog(_write(tmp_path, _doc([_m("l1", "light"), _m("l2", "light"), _m("s1", "standard")])))
    assert c.choose("h", "light", frozenset()).id == "l1"
    assert c.choose("h", "light", frozenset({"l1"})).id == "l2"
    assert c.choose("h", "light", frozenset({"l1", "l2"})).id == "s1"  # nothing left in light: go UP, never down
    assert c.choose("h", "heavy", frozenset()) is None  # nothing at heavy or above


def test_choose_respects_aliases_and_never_goes_down(tmp_path):
    c = load_catalog(_write(tmp_path, _doc([_m("f1", "frontier", ["fa"]), _m("h1", "heavy")])))
    assert c.choose("h", "frontier", frozenset({"fa"})) is None  # denied by alias, and there is nothing above frontier
    assert c.choose("h", "heavy", frozenset({"f1"})).id == "h1"


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema=1),
    lambda d: d["harnesses"]["h"]["models"][0].update(input=1.0),  # prices are not allowed in the catalog
    lambda d: d["harnesses"]["h"]["models"][0].update(tier="huge"),
    lambda d: d["harnesses"]["h"]["models"].append(_m("l1", "light")),  # duplicate name
    lambda d: d["harnesses"]["h"]["models"][0].update(id="bad name!"),
    lambda d: d["harnesses"].update(h=None),
])
def test_catalog_rejects_bad_input(tmp_path, mutate):
    doc = _doc([_m("l1", "light")])
    mutate(doc)
    with pytest.raises(ValueError):
        load_catalog(_write(tmp_path, doc))
