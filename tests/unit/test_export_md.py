import re
from datetime import date

import pytest
from chats import chat, turn
from secrets_corpus import SECRETS
from yardmaster.cli import main
from yardmaster.export_md import export_md
from yardmaster.timeutil import DateRange

R = DateRange(date(2026, 9, 4), date(2026, 9, 22), "2026-09-04_2026-09-22")


def _chats():
    return [
        chat("a", [turn("user", "plan it"), turn("assistant", "plan done", "opus", 10, 5)], harness="vscode-copilot",
             credits=2.5, models={"opus": 2.5}, workspace="C:\\ws\\app", title="Planning"),
        chat("b", [turn("user", "hi"), turn("assistant", "yo", "sonnet", 1_000, 500)], credits=None, models={"sonnet": 500.0}),
    ]


def test_layout_has_summary_models_index_and_full_content(tmp_path):
    out = export_md(_chats(), R, tmp_path, pii=False)
    assert out == tmp_path / "2026-09-04_2026-09-22.md"
    t = out.read_text(encoding="utf-8")
    assert t.startswith("# AI chats 2026-09-04 .. 2026-09-22")
    for section in ("## Summary", "## Credits and tokens by model", "## Index"):
        assert section in t
    assert "## 1. vscode-copilot a" in t and "## 2. claude-code b" in t and "plan done" in t
    assert re.search(r"\| \[1\]\(#1-vscode-copilot-a\) \| vscode-copilot \|", t)  # index links resolve to the headings
    assert "**Credits:** 2.5000" in t and "| opus |" in t


def test_everything_is_redacted(tmp_path):
    secret = SECRETS["github-pat"]
    c = chat("s", [turn("user", f"my token {secret}"), turn("tool", f"AWS {SECRETS['aws-access-key']}")], workspace=f"/w/{secret}",
             title=f"t {secret}")
    t = export_md([c], R, tmp_path, pii=False).read_text(encoding="utf-8")
    assert secret not in t and SECRETS["aws-access-key"] not in t and "[REDACTED:github-pat]" in t


def test_pii_flag(tmp_path):
    c = chat("p", [turn("user", "mail me at a.b@example.com")], workspace="C:\\Users\\rick\\proj")
    assert "a.b@example.com" in export_md([c], R, tmp_path / "x", pii=False).read_text(encoding="utf-8")
    t = export_md([c], R, tmp_path / "y", pii=True).read_text(encoding="utf-8")
    assert "a.b@example.com" not in t and "rick" not in t


def test_fence_is_longer_than_any_backtick_run_in_the_text(tmp_path):
    c = chat("f", [turn("user", "code:\n```py\nx\n``````\nend")])
    t = export_md([c], R, tmp_path, pii=False).read_text(encoding="utf-8")
    assert "\n```````\n" in t  # 7 backticks fence a text containing a run of 6


def test_existing_file_needs_overwrite(tmp_path):
    export_md(_chats(), R, tmp_path, pii=False)
    with pytest.raises(FileExistsError):
        export_md(_chats(), R, tmp_path, pii=False)
    export_md(_chats(), R, tmp_path, pii=False, overwrite=True)


def test_export_refuses_in_git_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "docs" / "out"
    with pytest.raises(PermissionError, match="git"):
        export_md(_chats(), R, sub, pii=False)
    assert not sub.exists()
    assert export_md(_chats(), R, sub, pii=False, force=True).is_file()


def test_empty_export(tmp_path):
    t = export_md([], R, tmp_path, pii=False).read_text(encoding="utf-8")
    assert "No chats" in t


def test_cli_export_md(tmp_path, home, capsys):
    from synthetic import copilot_home

    h = copilot_home(tmp_path / "cli")
    out = tmp_path / "out"
    args = ["export-md", "--from", "2026-09-04", "--to", "2026-09-22", "--harness", "copilot-cli", "--path", f"copilot-cli={h}",
            "--out", str(out)]
    assert main(args) == 0 and (out / "2026-09-04_2026-09-22.md").is_file()
    assert main(args) == 2 and "already exists" in capsys.readouterr().out  # needs --overwrite
    assert main([*args, "--overwrite"]) == 0
