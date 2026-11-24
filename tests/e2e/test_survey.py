import json
import os
import sys
from pathlib import Path

import pytest
from synthetic import copilot_home, vscode_user
from synthetic_claude import claude_home
from yardmaster import paths
from yardmaster.cli import main

RANGE = ["--from", "2026-09-04", "--to", "2026-09-22"]


@pytest.fixture
def trees(tmp_path, home):
    return {
        "vscode-copilot": vscode_user(tmp_path / "vs"),
        "copilot-cli": copilot_home(tmp_path / "cli"),
        "claude-code": claude_home(tmp_path / "cc"),
        "codex": tmp_path / "no-codex",
    }


def _args(trees, *extra):
    out = ["survey", *RANGE]
    for h, p in trees.items():
        out += ["--path", f"{h}={p}"]
    return [*out, *extra]


def test_survey_writes_batches_and_reports(trees, tmp_path, capsys):
    out = tmp_path / "batches"
    assert main(_args(trees, "--yes-expensive", "--out", str(out))) == 0
    text = capsys.readouterr().out
    assert "claude-code" in text and "no chats found for codex" in text and "Workspaces" in text
    assert (out / "batch-001.txt").is_file() and (out / "manifest.json").is_file()
    assert "UNTRUSTED" in (out / "batch-001.txt").read_text(encoding="utf-8")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "claude-code:sessMain" in manifest["chat_ids"] and "vscode-copilot:sessA" in manifest["chat_ids"]


def test_survey_empty_history(tmp_path, home, capsys):
    nothing = {h: tmp_path / "none" / h for h in ("vscode-copilot", "copilot-cli", "claude-code", "codex")}
    out = tmp_path / "batches"
    assert main(_args(nothing, "--out", str(out))) == 0
    text = capsys.readouterr().out
    assert "no chats found for vscode-copilot" in text and "no chats found for codex" in text
    assert not out.exists() and not paths.state_dir(os.environ, sys.platform).exists()


def test_cost_gate_exit_3(trees, tmp_path, capsys):
    out = tmp_path / "batches"
    assert main(_args(trees, "--out", str(out))) == 3
    assert "--yes-expensive" in capsys.readouterr().out and not out.exists()


def test_batch_count_guard_exit_4(trees, tmp_path, capsys):
    cfg = paths.config_dir(os.environ, sys.platform)
    cfg.mkdir(parents=True)
    (cfg / "config.toml").write_text("max_batches = 1\n")
    out = tmp_path / "batches"
    assert main(_args(trees, "--yes-expensive", "--batch-tokens", "300", "--out", str(out))) == 4
    assert "max_batches" in capsys.readouterr().out and not out.exists()


def test_exclude_workspace(trees, tmp_path):
    out = tmp_path / "batches"
    assert main(_args(trees, "--yes-expensive", "--exclude-workspace", "C:\\ws\\other", "--out", str(out))) == 0
    ids = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["chat_ids"]
    assert "claude-code:sessOther" not in ids and "copilot-cli:cliLate" not in ids and "claude-code:sessMain" in ids


def test_project_flag_keeps_only_that_workspace(trees, tmp_path):
    out = tmp_path / "batches"
    assert main(_args(trees, "--yes-expensive", "--project", "C:\\ws\\other", "--out", str(out))) == 0
    ids = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["chat_ids"]
    assert ids == ["claude-code:sessOther", "copilot-cli:cliLate"]


def test_harness_filter_and_unknown_harness(trees, tmp_path, capsys):
    out = tmp_path / "batches"
    assert main(_args(trees, "--yes-expensive", "--harness", "claude-code", "--out", str(out))) == 0
    ids = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["chat_ids"]
    assert all(i.startswith("claude-code:") for i in ids)
    assert main(_args(trees, "--harness", "nope")) == 2


def test_policy_harness_restriction_applies(trees, tmp_path, monkeypatch):
    from yardmaster import settings

    real = settings.load_settings
    pol = tmp_path / "policy.toml"
    pol.write_text('harnesses = ["codex"]\n')
    monkeypatch.setattr("yardmaster.cli.load_settings", lambda env, platform: real(env, platform, policy=pol))
    out = tmp_path / "batches"
    assert main(_args(trees, "--yes-expensive", "--out", str(out))) == 0
    assert not out.exists()  # policy limited it to codex, which has no history here


def test_default_survey_dir_preview_and_clean(trees, capsys):
    assert main(_args(trees, "--yes-expensive")) == 0
    d = Path(next(line.split(": ", 1)[1] for line in capsys.readouterr().out.splitlines() if line.startswith("Batches written to: ")))
    assert (d / "batch-001.txt").is_file()
    assert main(["preview", "1"]) == 0
    assert "UNTRUSTED" in capsys.readouterr().out
    assert main(["preview", "99"]) == 2
    assert main(["clean"]) == 0 and not d.exists()
    assert main(["clean"]) == 0  # idempotent


def test_ledger_command_needs_no_model(trees, capsys):
    assert main(["ledger", *RANGE, *[a for h, p in trees.items() for a in ("--path", f"{h}={p}")]]) == 0
    out = capsys.readouterr().out
    assert "vscode-copilot" in out and "claude-code" in out and "Fresh tokens" in out and "plan the migration" not in out


def test_second_survey_replaces_the_first_directory(trees, capsys):
    def run():
        assert main(_args(trees, "--yes-expensive")) == 0
        return Path(next(ln.split(": ", 1)[1] for ln in capsys.readouterr().out.splitlines() if ln.startswith("Batches written to: ")))

    first = run()
    second = run()
    assert second.exists() and not first.exists()  # no orphaned chat data left in the temp dir
    main(["clean"])
