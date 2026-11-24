import json
import re
from pathlib import Path

import yaml
from yardmaster.catalog import default_catalog
from yardmaster.cli import _build_parser
from yardmaster.schema import validate_plan, validate_verdicts

SKILL = Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "SKILL.md"
TEXT = SKILL.read_text(encoding="utf-8")


def _sections() -> dict[str, str]:
    parts = re.split(r"(?m)^## ", TEXT)
    return {p.split("\n", 1)[0].strip(): p for p in parts[1:]}


def _subparsers():
    return next(a for a in _build_parser()._actions if a.dest == "cmd").choices


def test_front_matter():
    head = TEXT.split("---\n")[1]
    fm = yaml.safe_load(head)
    assert set(fm) == {"name", "description"} and fm["name"] == "yardmaster"
    assert 40 < len(fm["description"]) <= 1024
    for trigger in ("/yardmaster", "model router"):
        assert trigger in fm["description"]


def test_every_command_and_flag_named_in_the_skill_exists():
    subs = _subparsers()
    used = set()
    for line in TEXT.splitlines():
        m = re.search(r"\$YM\s+([a-z][a-z-]*)(.*)", line)
        if not m:
            continue
        cmd, rest = m.groups()
        assert cmd in subs, f"unknown command in SKILL.md: {cmd}"
        used.add(cmd)
        for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", rest):
            assert flag in subs[cmd]._option_string_actions, f"{cmd} has no {flag}"
    assert {"doctor", "survey", "preview", "validate", "route", "clean", "ledger", "undo"} <= used


def test_json_examples_validate_against_the_real_schemas():
    catalog = default_catalog()
    blocks = dict(re.findall(r"```json (verdicts|plan)\n(.*?)\n```", TEXT, re.S))
    assert set(blocks) == {"verdicts", "plan"}
    verdicts = validate_verdicts(json.loads(blocks["verdicts"]), manifest_ids={"claude-code:example"}, catalog=catalog)
    assert len(verdicts) == 1
    plan = validate_plan(json.loads(blocks["plan"]), catalog=catalog)
    assert len(plan.groups) >= 2


def test_apply_appears_only_in_the_apply_step():
    sec = _sections()
    holders = [name for name, body in sec.items() if "--apply" in body]
    assert len(holders) == 1 and holders[0].startswith("Step 7"), holders


def test_steps_are_present_in_order_and_python_bootstrap_is_described():
    names = list(_sections())
    steps = [n for n in names if n.startswith("Step ")]
    assert [n.split(":")[0] for n in steps] == [f"Step {i}" for i in range(1, 8)]
    for needle in ("python3", "py -3", "3.11", "winget", "brew", "apt"):
        assert needle in _sections()[steps[0]]


def test_safety_rules_cover_untrusted_data_and_consent():
    safety = _sections()["Safety rules (read first)"].lower()
    for needle in ("untrusted", "never paste", "injection suspected", "explicit"):
        assert needle in safety
    assert "ignore previous instructions" in TEXT.lower() or "ignore" in safety


def test_user_gate_before_analysis_and_before_apply():
    sec = _sections()
    assert "ask" in sec["Step 2: survey"].lower() and "--yes-expensive" in sec["Step 2: survey"]
    assert "explicit" in sec["Step 7: apply"].lower() and "yes" in sec["Step 7: apply"].lower()
    assert "never" in sec["Step 6: preview"].lower() or "do not" in sec["Step 6: preview"].lower()
