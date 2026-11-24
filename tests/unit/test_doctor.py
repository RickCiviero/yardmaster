from datetime import date

from synthetic_claude import claude_home
from yardmaster import doctor as doctor_mod
from yardmaster.cli import main
from yardmaster.doctor import doctor, render_doctor

TODAY = date(2026, 11, 24)


def _rows(env, tmp_path, **kw):
    rows = doctor(env, "linux", today=TODAY, policy=tmp_path / "no-policy.toml", config=tmp_path / "no-config.toml", **kw)
    return {name: (status, detail) for name, status, detail in rows}


def test_missing_harness_history_is_a_warning_not_a_failure(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "x")}
    rows = _rows(env, tmp_path)
    for h in ("vscode-copilot", "copilot-cli", "claude-code", "codex"):
        assert rows[f"history:{h}"][0] == "warn" and "not found" in rows[f"history:{h}"][1]
    assert not [n for n, (s, _) in rows.items() if s == "fail"]


def test_present_history_is_counted(tmp_path):
    root = tmp_path / "c"
    env = {"HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(claude_home(root))}
    status, detail = _rows(env, tmp_path)["history:claude-code"]
    assert status == "ok" and "3 session files" in detail


def test_python_too_old_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor_mod.sys, "version_info", (3, 10, 9, "final", 0))
    assert _rows({"HOME": str(tmp_path)}, tmp_path)["python"][0] == "fail"
    monkeypatch.undo()
    assert _rows({"HOME": str(tmp_path)}, tmp_path)["python"][0] == "ok"


def test_unverified_formats_are_reported(tmp_path):
    rows = _rows({"HOME": str(tmp_path)}, tmp_path)
    assert rows["format:vscode-copilot"][0] == "ok"
    for h in ("copilot-cli", "claude-code", "codex"):
        assert rows[f"format:{h}"][0] == "warn" and "not verified" in rows[f"format:{h}"][1]


def test_pricing_unverified_and_age(tmp_path):
    status, detail = _rows({"HOME": str(tmp_path)}, tmp_path)["pricing"]
    assert status == "warn" and "UNVERIFIED" in detail
    old = doctor({"HOME": str(tmp_path)}, "linux", today=date(2027, 6, 1), policy=tmp_path / "n", config=tmp_path / "n")
    assert "days old" in next(d for n, _, d in old if n == "pricing")


def test_broken_policy_fails_the_settings_check(tmp_path):
    bad = tmp_path / "policy.toml"
    bad.write_text("deny_models = 'opus'\n")
    rows = doctor({"HOME": str(tmp_path)}, "linux", today=TODAY, policy=bad, config=tmp_path / "n")
    status, detail = next((s, d) for n, s, d in rows if n == "settings")
    assert status == "fail" and "policy" in detail


def test_effective_settings_show_their_sources(tmp_path):
    pol = tmp_path / "policy.toml"
    pol.write_text('deny_models = ["opus"]\nmax_batches = 5\n')
    rows = doctor({"HOME": str(tmp_path)}, "linux", today=TODAY, policy=pol, config=tmp_path / "n")
    detail = next(d for n, _, d in rows if n == "settings")
    assert "opus" in detail and "max_batches=5 (policy)" in detail


def test_write_targets_checked(tmp_path):
    rows = _rows({"HOME": str(tmp_path)}, tmp_path)
    assert rows["write:project"][0] == "ok"
    assert all(rows[f"write:{h}"][0] in ("ok", "warn") for h in ("claude-code", "codex", "copilot-cli"))


def test_render_and_cli_exit_codes(tmp_path, capsys, monkeypatch):
    text = render_doctor(doctor({"HOME": str(tmp_path)}, "linux", today=TODAY, policy=tmp_path / "n", config=tmp_path / "n"))
    assert "python" in text and "pricing" in text and "settings" in text
    assert main(["doctor"]) in (0, 1)
    assert "python" in capsys.readouterr().out
