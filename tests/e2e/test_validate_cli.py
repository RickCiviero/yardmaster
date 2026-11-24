import json

import pytest
from yardmaster.cli import main

V = {"chat_id": "claude-code:c1", "task_group": "build-and-fix", "task_summary": "Built a parser", "model_used": "opus",
     "outcome": "ok", "sufficient_tier": "standard", "cheapest_sufficient_model": "sonnet", "confidence": 0.9,
     "reason": "Routine change"}
PLAN = {"version": 1, "description": "d", "groups": [{"name": "build-and-fix", "tier": "standard", "when": "Building code.",
                                                          "examples": [], "chats": 1, "prefer": {}}]}


@pytest.fixture
def manifest(tmp_path):
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps({"chat_ids": ["claude-code:c1"], "batches": []}))
    return m


def _w(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return p


def test_validate_verdicts_ok_and_invalid(tmp_path, manifest, capsys):
    assert main(["validate", "verdicts", str(_w(tmp_path, "v.json", [V])), "--manifest", str(manifest)]) == 0
    assert "OK: 1 verdicts" in capsys.readouterr().out
    bad = _w(tmp_path, "bad.json", [V | {"cheapest_sufficient_model": "gpt-evil SECRET-TEXT"}])
    assert main(["validate", "verdicts", str(bad), "--manifest", str(manifest)]) == 1
    out = capsys.readouterr().out
    assert "INVALID" in out and "/0/cheapest_sufficient_model" in out and "SECRET-TEXT" not in out


def test_validate_plan(tmp_path, capsys):
    assert main(["validate", "plan", str(_w(tmp_path, "p.json", PLAN))]) == 0
    assert "OK: plan with 1 groups" in capsys.readouterr().out
    assert main(["validate", "plan", str(_w(tmp_path, "p2.json", PLAN | {"version": 3}))]) == 1


def test_validate_unreadable_inputs(tmp_path, manifest, capsys):
    assert main(["validate", "plan", str(tmp_path / "missing.json")]) == 2
    (tmp_path / "junk.json").write_text("{nope")
    assert main(["validate", "plan", str(tmp_path / "junk.json")]) == 2
    assert main(["validate", "verdicts", str(_w(tmp_path, "v.json", [V]))]) == 2  # no survey dir and no --manifest
    assert main(["validate", "verdicts", str(_w(tmp_path, "v.json", [V])), "--manifest", str(tmp_path / "none.json")]) == 2
    assert "error" in capsys.readouterr().out.lower()
