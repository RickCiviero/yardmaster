from pathlib import Path

import pytest
from yardmaster.catalog import TIERS, load_catalog
from yardmaster.resolve import ResolvedGroup, resolve_plan
from yardmaster.schema import Group, Plan, ValidationError

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "scripts" / "yardmaster" / "models.json")


def _g(name, tier, when, examples=(), prefer=None):
    return Group(name, tier, when, list(examples), 1, prefer or {})


def _plan(*groups):
    return Plan(1, "d", list(groups))


NONE = frozenset()


def test_resolve_merges_same_model():
    plan = _plan(_g("quick-questions", "light", "Quick answers.", ["where a file is", "a setting"]),
                 _g("tiny-chores", "light", "Small chores.", ["rename a variable", "fix a typo"]))
    (g,) = resolve_plan(plan, "claude-code", CATALOG, NONE)
    assert isinstance(g, ResolvedGroup) and g.model.id == "haiku" and g.tier == "light" and g.name == "quick-questions"
    assert g.when == "Quick answers; Small chores."
    assert g.examples == ["where a file is", "a setting", "rename a variable"]  # capped at 3


def test_resolve_respects_deny_and_falls_up():
    plan = _plan(_g("quick-questions", "light", "Quick."))
    assert resolve_plan(plan, "claude-code", CATALOG, frozenset({"haiku"}))[0].model.id == "sonnet"
    assert resolve_plan(plan, "claude-code", CATALOG, frozenset({"claude-haiku-5-5"}))[0].model.id == "sonnet"  # by alias


def test_resolve_orders_the_strongest_tier_first():
    plan = _plan(_g("quick", "light", "Q."), _g("build", "standard", "B."), _g("plan-hard", "heavy", "P."))
    assert [g.model.id for g in resolve_plan(plan, "claude-code", CATALOG, NONE)] == ["opus", "sonnet", "haiku"]
    tiers = [g.model.tier for g in resolve_plan(plan, "vscode-copilot", CATALOG, NONE)]
    assert tiers == sorted(tiers, key=TIERS.index, reverse=True)


def test_resolve_honours_prefer_unless_denied():
    plan = _plan(_g("build", "standard", "B.", prefer={"codex": "gpt-6.2-sol"}))
    assert resolve_plan(plan, "codex", CATALOG, NONE)[0].model.id == "gpt-6.2-sol"
    assert resolve_plan(plan, "codex", CATALOG, frozenset({"gpt-6.2-sol"}))[0].model.id == "gpt-6.1-terra"
    assert resolve_plan(plan, "claude-code", CATALOG, NONE)[0].model.id == "sonnet"  # prefer is per harness


def test_merged_group_takes_highest_tier_and_its_name():
    plan = _plan(_g("quick", "light", "Q."), _g("build", "standard", "B."), _g("plan-hard", "heavy", "P."))
    (g,) = resolve_plan(plan, "claude-code", CATALOG, frozenset({"haiku", "sonnet"}))  # everything lands on opus
    assert g.model.id == "opus" and g.tier == "heavy" and g.name == "plan-hard" and g.when == "P; B; Q."


def test_when_without_trailing_period_stays_without():
    plan = _plan(_g("a-group", "light", "Quick answers"), _g("b-group", "light", "Small chores"))
    assert resolve_plan(plan, "claude-code", CATALOG, NONE)[0].when == "Quick answers; Small chores"


def test_no_model_available_raises():
    plan = _plan(_g("quick", "light", "Q."))
    deny = frozenset({"haiku", "sonnet", "opus", "claude-fable-5-1"})
    with pytest.raises(ValidationError, match="no model"):
        resolve_plan(plan, "claude-code", CATALOG, deny)
    with pytest.raises(ValidationError, match="no model"):
        resolve_plan(plan, "unknown-harness", CATALOG, frozenset())


def test_a_group_that_is_not_merged_keeps_its_text_exactly():
    for when in ("Quick answers..", "Quick answers.  ", "Quick answers", "..", "x."):
        (g,) = resolve_plan(_plan(_g("quick", "light", when)), "claude-code", CATALOG, NONE)
        assert g.when == when.strip(), when
