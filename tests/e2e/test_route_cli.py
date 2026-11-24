import json
import os
import re
import sys
from dataclasses import asdict

import pytest
from yardmaster import paths
from yardmaster.cli import main
from yardmaster.schema import Group, Plan

PLAN = Plan(1, "CLI test plan", [
    Group("build-and-fix", "heavy", "Building code over many steps.", ["a feature"], 3, {}),
    Group("quick-questions", "light", "Quick answers.", ["a lookup"], 5, {}),
])


@pytest.fixture
def setup(tmp_path, home, monkeypatch):
    for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "TERM_PROGRAM", "ANTHROPIC_MODEL"):
        monkeypatch.delenv(k, raising=False)
    for k in [k for k in os.environ if k.startswith(("CODEX_", "COPILOT_"))]:
        monkeypatch.delenv(k)
    proj = tmp_path / "proj"
    proj.mkdir()
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(asdict(PLAN)))
    return proj, plan


def _dry(capsys, proj, plan, *extra):
    rc = main(["route", "--plan", str(plan), "--root", str(proj), "--dry-run", *extra])
    out = capsys.readouterr().out
    m = re.search(r"Run id: (\S+)\nApproval code: (\S+)", out)
    return rc, out, m.groups() if m else (None, None)


def test_dry_run_then_apply_then_undo(setup, capsys):
    proj, plan = setup
    rc, out, (run_id, code) = _dry(capsys, proj, plan, "--target", "claude-code")
    assert rc == 0 and "=== " in out and not (proj / "CLAUDE.md").exists()
    assert main(["route", "--apply", run_id, "--code", "WRONG"]) == 1
    assert "approval code" in capsys.readouterr().out and not (proj / "CLAUDE.md").exists()
    assert main(["route", "--apply", run_id, "--code", code]) == 0
    assert (proj / "CLAUDE.md").is_file() and (proj / ".claude" / "agents" / "ym-quick-questions.md").is_file()
    assert main(["route", "--apply", run_id, "--code", code]) == 1  # applied once only
    assert main(["undo"]) == 0
    assert not (proj / "CLAUDE.md").exists() and not (proj / ".claude").exists()
    assert main(["undo"]) == 1  # nothing left to undo
    assert "nothing to undo" in capsys.readouterr().out


def test_target_auto_uses_the_running_harness(setup, capsys, monkeypatch):
    proj, plan = setup
    rc, out, _ = _dry(capsys, proj, plan, "--target", "auto")
    assert rc == 2 and "--target" in out  # cannot tell which harness this is
    monkeypatch.setenv("CLAUDECODE", "1")
    rc, out, ids = _dry(capsys, proj, plan, "--target", "auto")
    assert rc == 0 and ids[0] and "CLAUDE.md" in out


def test_target_all_covers_every_harness_and_is_reversible(setup, capsys, home):
    proj, plan = setup
    rc, out, (run_id, code) = _dry(capsys, proj, plan, "--target", "all")
    assert rc == 0
    for needle in (".agents", "ym-build-and-fix.agent.md", "CLAUDE.md", "ym-build-and-fix.config.toml", "AGENTS.md"):
        assert needle in out
    assert main(["route", "--apply", run_id, "--code", code]) == 0
    assert (proj / ".agents" / "model-router" / "yardmaster.model-router.yml").is_file()
    assert (proj / "AGENTS.md").read_text(encoding="utf-8").count("yardmaster:begin") == 2  # copilot-cli + codex
    codex_profile = next(home.rglob("ym-build-and-fix.config.toml"))
    assert 'model = "gpt-5"' in codex_profile.read_text(encoding="utf-8")
    assert main(["undo", run_id]) == 0
    assert not (proj / "AGENTS.md").exists() and not (proj / ".agents").exists() and not codex_profile.exists()


def test_argument_errors(setup, capsys, tmp_path):
    proj, plan = setup
    assert main(["route", "--target", "claude-code", "--dry-run"]) == 2  # no --plan
    assert main(["route", "--plan", str(plan), "--target", "nope", "--dry-run"]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(asdict(PLAN) | {"version": 9}))
    assert main(["route", "--plan", str(bad), "--root", str(proj), "--target", "claude-code", "--dry-run"]) == 1
    assert "INVALID" in capsys.readouterr().out
    assert main(["route", "--target", "claude-code"]) == 2  # neither --dry-run nor --apply
    assert main(["route", "--apply", "../../x"]) == 1


def test_state_lives_in_the_state_dir(setup, capsys):
    proj, plan = setup
    _, _, (run_id, _) = _dry(capsys, proj, plan, "--target", "claude-code")
    assert (paths.state_dir(os.environ, sys.platform) / "runs" / run_id / "record.json").is_file()
