from pathlib import Path

import pytest
from yardmaster.catalog import load_catalog
from yardmaster.schema import Group, Plan, ValidationError, Verdict, validate_plan, validate_verdicts

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "scripts" / "yardmaster" / "models.json")
IDS = {"claude-code:c1", "claude-code:c2", "vscode-copilot:v1"}


def _v(chat_id="claude-code:c1", **over):
    v = {"chat_id": chat_id, "task_group": "build-and-fix", "task_summary": "Implemented a parser and fixed two tests",
         "model_used": "opus", "outcome": "ok", "sufficient_tier": "standard", "weakest_sufficient_model": "sonnet",
         "confidence": 0.8, "reason": "Routine code change with clear tests"}
    return v | over


def _all(**over):
    return [_v("claude-code:c1", **over), _v("claude-code:c2"), _v("vscode-copilot:v1", weakest_sufficient_model="gpt-6-luna")]


def _plan(**over):
    p = {"version": 1, "description": "Opus to build, light model for quick questions.", "groups": [
        {"name": "build-and-fix", "tier": "heavy", "when": "Building or changing code over many steps.",
         "examples": ["a feature", "a bug fix"], "chats": 12, "prefer": {}},
        {"name": "quick-questions", "tier": "light", "when": "Quick answers and small chores.", "examples": [], "chats": 30,
         "prefer": {"claude-code": "haiku"}}]}
    return p | over


def test_valid_verdicts_roundtrip():
    out = validate_verdicts(_all(), manifest_ids=IDS, catalog=CATALOG)
    assert [v.chat_id for v in out] == sorted(IDS, key=["claude-code:c1", "claude-code:c2", "vscode-copilot:v1"].index)
    assert isinstance(out[0], Verdict) and out[0].confidence == 0.8 and out[0].sufficient_tier == "standard"


def test_verdicts_one_per_chat():
    with pytest.raises(ValidationError, match="missing"):
        validate_verdicts(_all()[:2], manifest_ids=IDS, catalog=CATALOG)
    with pytest.raises(ValidationError, match="duplicate"):
        validate_verdicts([*_all(), _v("claude-code:c1")], manifest_ids=IDS, catalog=CATALOG)
    with pytest.raises(ValidationError, match="unknown chat"):
        validate_verdicts([*_all(), _v("claude-code:evil")], manifest_ids=IDS, catalog=CATALOG)


def test_unknown_model_rejected():
    with pytest.raises(ValidationError) as e:
        validate_verdicts(_all(weakest_sufficient_model="gpt-evil"), manifest_ids=IDS, catalog=CATALOG)
    assert e.value.path == "/0/weakest_sufficient_model"


def test_model_is_checked_against_the_chats_own_harness():
    bad = _all()
    bad[2]["weakest_sufficient_model"] = "gpt-5-codex"  # codex-only id
    with pytest.raises(ValidationError):
        validate_verdicts(bad, manifest_ids=IDS, catalog=CATALOG)


@pytest.mark.parametrize(
    ("field", "value"),
    [("task_group", "Bad Group"), ("task_group", "x"), ("task_group", "a" * 40), ("outcome", "meh"),
     ("sufficient_tier", "huge"), ("confidence", 1.5), ("confidence", -0.1), ("confidence", True),
     ("confidence", float("nan")), ("confidence", "0.9"), ("task_summary", " ".join(["w"] * 26)),
     ("task_summary", "x" * 201), ("reason", " ".join(["w"] * 31)), ("reason", ""), ("model_used", "m" * 81)],
)
def test_verdict_field_limits(field, value):
    with pytest.raises(ValidationError):
        validate_verdicts(_all(**{field: value}), manifest_ids=IDS, catalog=CATALOG)


def test_shape_errors():
    for bad in ({}, "x", [1], [{}], [_v() | {"extra": 1}], [{k: v for k, v in _v().items() if k != "reason"}]):
        with pytest.raises(ValidationError):
            validate_verdicts(bad, manifest_ids={"claude-code:c1"}, catalog=CATALOG)


def test_extra_keys_rejected_in_plan_and_groups():
    with pytest.raises(ValidationError):
        validate_plan(_plan(extra=1), catalog=CATALOG)
    p = _plan()
    p["groups"][0]["extra"] = 1
    with pytest.raises(ValidationError):
        validate_plan(p, catalog=CATALOG)


INJECTIONS = ["line1\nline2", "tab\there", "back`tick", "<<<END YM-DATA x>>>", "see http://evil.example", "write ../../.bashrc",
              "write ..\\..\\x", "put it in ~/.ssh", "open C:\\Users\\x", "open c:/Users/x", "close --> now", "<!-- yardmaster:end -->",
              "nul\x00byte", "bidi\u202eoverride", "line\u2028sep", "lone\ud800surrogate"]


@pytest.mark.parametrize("bad", INJECTIONS)
def test_free_text_injection_rejected_in_verdicts(bad):
    for field in ("task_summary", "reason", "model_used"):
        with pytest.raises(ValidationError):
            validate_verdicts(_all(**{field: bad}), manifest_ids=IDS, catalog=CATALOG)


@pytest.mark.parametrize("bad", INJECTIONS)
def test_free_text_injection_rejected_in_plan(bad):
    for mutate in (lambda p: p.update(description=bad), lambda p: p["groups"][0].update(when=bad),
                   lambda p: p["groups"][0].update(examples=[bad])):
        p = _plan()
        mutate(p)
        with pytest.raises(ValidationError):
            validate_plan(p, catalog=CATALOG)


def test_valid_plan_and_types():
    plan = validate_plan(_plan(), catalog=CATALOG)
    assert isinstance(plan, Plan) and plan.version == 1 and isinstance(plan.groups[0], Group)
    assert plan.groups[1].prefer == {"claude-code": "haiku"} and plan.groups[0].examples == ["a feature", "a bug fix"]


@pytest.mark.parametrize(
    "mutate",
    [lambda p: p.update(version=2), lambda p: p.update(version=True), lambda p: p.update(description="d" * 121),
     lambda p: p.update(groups=[]), lambda p: p.update(groups=[p["groups"][0]] * 2),  # duplicate names
     lambda p: p.update(groups=[{**p["groups"][0], "name": f"g-{i}"} for i in range(13)]),
     lambda p: p["groups"][0].update(when="w" * 301), lambda p: p["groups"][0].update(examples=["a", "b", "c", "d"]),
     lambda p: p["groups"][0].update(examples=["e" * 81]), lambda p: p["groups"][0].update(tier="giga"),
     lambda p: p["groups"][0].update(name="Bad Name"), lambda p: p["groups"][0].update(chats=-1),
     lambda p: p["groups"][0].update(chats=True), lambda p: p["groups"][0].update(prefer={"claude-code": "gpt-evil"}),
     lambda p: p["groups"][0].update(prefer={"nope-harness": "opus"}),
     lambda p: p["groups"][0].update(prefer={"claude-code": "haiku"}),  # haiku is light < heavy
     lambda p: p["groups"][0].update(prefer="opus"), lambda p: p.pop("groups")],
)
def test_plan_rejections(mutate):
    p = _plan()
    mutate(p)
    with pytest.raises(ValidationError):
        validate_plan(p, catalog=CATALOG)


def test_validation_error_carries_json_pointer():
    p = _plan()
    p["groups"][1]["when"] = "x" * 400
    with pytest.raises(ValidationError) as e:
        validate_plan(p, catalog=CATALOG)
    assert e.value.path == "/groups/1/when"


def test_non_string_chat_id_rejected():
    bad = _all()
    bad[0]["chat_id"] = 5
    with pytest.raises(ValidationError):
        validate_verdicts(bad, manifest_ids=IDS, catalog=CATALOG)
