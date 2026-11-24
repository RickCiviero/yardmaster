import json
import os
import stat
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
from yardmaster import route, writers
from yardmaster.pricing import load_pricing
from yardmaster.route import RouteError, apply, dry_run, undo
from yardmaster.schema import Group, Plan, ValidationError
from yardmaster.settings import Settings

pytestmark = pytest.mark.pentest  # the TOCTOU / rollback / tamper cases double as pentests
PRICING = load_pricing(Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "pricing.json")
PLAN = Plan(1, "Plan test", [
    Group("build-and-fix", "heavy", "Building code over many steps.", ["a feature"], 3, {}),
    Group("quick-questions", "light", "Quick answers.", ["a lookup"], 5, {}),
])
NO_POLICY = Settings(frozenset(), None, False, 40, {})


@pytest.fixture(autouse=True)
def fixed_date(monkeypatch):
    monkeypatch.setattr(writers, "today", lambda: "2026-11-23")


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    state = tmp_path / "state"
    monkeypatch.setattr(route, "state_dir", lambda env, platform: state)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(asdict(PLAN)))
    env = {"HOME": str(home), "USERPROFILE": str(home)}
    return type("Ctx", (), {"home": home, "proj": proj, "state": state, "plan": plan, "env": env})()


def _dry(ctx, targets=("vscode-copilot",), global_=False, settings=NO_POLICY):
    return dry_run(ctx.plan, list(targets), ctx.proj, global_, ctx.env, sys.platform, settings=settings, pricing=PRICING)


def _apply(ctx, rec, code=None, interactive=False):
    return apply(rec.run_id, code, interactive=interactive, env=ctx.env, platform=sys.platform)


ROUTER = ".agents/model-router/yardmaster.model-router.yml"


def test_dry_run_writes_nothing_but_the_record(ctx, capsys):
    rec = _dry(ctx)
    assert not (ctx.proj / ".agents").exists()
    out = capsys.readouterr().out
    assert f"Run id: {rec.run_id}" in out and f"Approval code: {rec.code}" in out
    assert f"+++ b/{ROUTER}" in out and "+  - model: " in out and "(new file)" in out
    assert len(rec.code) == 4 and rec.code.isalpha() and rec.code.isupper()
    rdir = ctx.state / "runs" / rec.run_id
    assert (rdir / "record.json").is_file() and (rdir / "report.md").is_file()
    report = (rdir / "report.md").read_text(encoding="utf-8")
    assert "vscode-copilot" in report and "yardmaster.model-router.yml (new)" in report


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_record_file_mode_0600(ctx):
    rec = _dry(ctx)
    assert stat.S_IMODE((ctx.state / "runs" / rec.run_id / "record.json").stat().st_mode) == 0o600


def test_apply_writes_exactly_the_previewed_text(ctx):
    rec = _dry(ctx)
    written = _apply(ctx, rec)
    assert written == [ctx.proj / ".agents" / "model-router" / "yardmaster.model-router.yml"]
    assert written[0].read_text(encoding="utf-8").replace("\r\n", "\n") == rec.changes[0]["new_text"]


def test_apply_requires_code_on_tty(ctx, monkeypatch):
    rec = _dry(ctx)
    monkeypatch.setattr("builtins.input", lambda prompt="": "NOPE")
    with pytest.raises(RouteError, match="approval code"):
        _apply(ctx, rec, interactive=True)
    assert not (ctx.proj / ".agents").exists()
    monkeypatch.setattr("builtins.input", lambda prompt="": rec.code.lower())  # case-insensitive, typed by a human
    assert len(_apply(ctx, rec, interactive=True)) == 1


def test_wrong_code_always_aborts_even_without_tty(ctx):
    rec = _dry(ctx)
    with pytest.raises(RouteError, match="approval code"):
        _apply(ctx, rec, code="ZZZZ" if rec.code != "ZZZZ" else "AAAA")
    assert not (ctx.proj / ".agents").exists()
    assert len(_apply(ctx, rec, code=rec.code)) == 1


def test_apply_twice_is_refused(ctx):
    rec = _dry(ctx)
    _apply(ctx, rec)
    with pytest.raises(RouteError, match="already applied"):
        _apply(ctx, rec)


def test_apply_aborts_if_target_changed_and_writes_nothing(ctx):
    (ctx.proj / "CLAUDE.md").write_bytes(b"# mine\n")
    rec = _dry(ctx, ("claude-code", "vscode-copilot"))
    (ctx.proj / "CLAUDE.md").write_bytes(b"# mine, edited after the preview\n")  # TOCTOU
    with pytest.raises(RouteError, match="changed since"):
        _apply(ctx, rec)
    assert (ctx.proj / "CLAUDE.md").read_bytes() == b"# mine, edited after the preview\n"
    assert not (ctx.proj / ".agents").exists() and not (ctx.proj / ".claude").exists()  # all-or-nothing


def test_apply_aborts_if_new_target_appeared(ctx):
    rec = _dry(ctx)
    p = ctx.proj / ROUTER
    p.parent.mkdir(parents=True)
    p.write_bytes(b"someone else wrote this\n")
    with pytest.raises(RouteError, match="changed since"):
        _apply(ctx, rec)
    assert p.read_bytes() == b"someone else wrote this\n"


def test_apply_aborts_if_parent_became_a_link(ctx, tmp_path):
    rec = _dry(ctx)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = ctx.proj / ".agents"
    if sys.platform == "win32":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        assert r.returncode == 0, r.stderr
    else:
        os.symlink(outside, link, target_is_directory=True)
    with pytest.raises(RouteError, match="link"):
        _apply(ctx, rec)
    assert list(outside.iterdir()) == []


def test_apply_rolls_back_on_midway_failure(ctx, monkeypatch):
    claude_md = ctx.proj / "CLAUDE.md"
    claude_md.write_bytes(b"\xef\xbb\xbf# mine\r\n")
    rec = _dry(ctx, ("claude-code",))
    real, calls = route.atomic_write, []

    def flaky(path, text, **kw):
        calls.append(path)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(path, text, **kw)

    monkeypatch.setattr(route, "atomic_write", flaky)
    with pytest.raises(OSError, match="disk full"):
        _apply(ctx, rec)
    assert len(calls) == 2
    assert not list((ctx.proj / ".claude").rglob("*.md"))  # the first, newly created file was removed
    assert claude_md.read_bytes() == b"\xef\xbb\xbf# mine\r\n"  # byte-exact (BOM + CRLF) if it had been touched


def test_rollback_restores_an_overwritten_existing_file(ctx, monkeypatch):
    agents = ctx.proj / ".claude" / "agents"
    agents.mkdir(parents=True)
    existing = agents / "ym-quick-questions.md"
    existing.write_bytes(b"old agent file\r\n")
    rec = _dry(ctx, ("claude-code",))
    paths = [Path(c["path"]) for c in rec.changes]
    real, n = route.atomic_write, [0]

    def fail_last(path, text, **kw):
        n[0] += 1
        if n[0] == len(paths):
            raise OSError("boom")
        return real(path, text, **kw)

    monkeypatch.setattr(route, "atomic_write", fail_last)
    with pytest.raises(OSError):
        _apply(ctx, rec)
    assert existing.read_bytes() == b"old agent file\r\n"


def test_undo_restores_existing_and_removes_new(ctx):
    mine = ctx.proj / "CLAUDE.md"
    mine.write_bytes(b"\xef\xbb\xbf# mine\r\nline two\r\n")
    rec = _dry(ctx, ("claude-code",))
    _apply(ctx, rec)
    assert b"yardmaster:begin" in mine.read_bytes() and (ctx.proj / ".claude" / "agents").exists()
    restored = undo(None, ctx.env, sys.platform)
    assert mine in restored
    assert mine.read_bytes() == b"\xef\xbb\xbf# mine\r\nline two\r\n"
    assert not list((ctx.proj / ".claude").rglob("*.md"))


def test_undo_refuses_if_user_edited_after(ctx):
    rec = _dry(ctx)
    (written,) = _apply(ctx, rec)
    written.write_bytes(written.read_bytes() + b"# my own tweak\n")
    with pytest.raises(RouteError, match="edited since"):
        undo(rec.run_id, ctx.env, sys.platform)
    assert b"my own tweak" in written.read_bytes()


def test_undo_nothing_to_undo_and_double_undo(ctx):
    with pytest.raises(RouteError, match="nothing to undo"):
        undo(None, ctx.env, sys.platform)
    rec = _dry(ctx)
    _apply(ctx, rec)
    undo(rec.run_id, ctx.env, sys.platform)
    with pytest.raises(RouteError, match="already undone|nothing to undo"):
        undo(rec.run_id, ctx.env, sys.platform)


@pytest.mark.parametrize("bad", ["../x", "..\\x", "a/b", "", "20261123T000000Z-zzzzzz", "x" * 300, "/etc/passwd"])
def test_run_id_must_be_well_formed(ctx, bad):
    with pytest.raises(RouteError, match="run id"):
        apply(bad, None, interactive=False, env=ctx.env, platform=sys.platform)
    with pytest.raises(RouteError, match="run id"):
        undo(bad, ctx.env, sys.platform)


def test_unknown_run_id(ctx):
    with pytest.raises(RouteError, match="no such run"):
        apply("20261123T000000Z-abcdef", None, interactive=False, env=ctx.env, platform=sys.platform)


def test_tampered_record_paths_outside_root_are_refused(ctx):
    rec = _dry(ctx)
    f = ctx.state / "runs" / rec.run_id / "record.json"
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc["changes"][0]["path"] = str(ctx.home / "evil.txt")
    f.write_text(json.dumps(doc))
    with pytest.raises(RouteError):
        _apply(ctx, rec)
    assert not (ctx.home / "evil.txt").exists()


def test_invalid_plan_is_rejected_before_anything(ctx):
    ctx.plan.write_text(json.dumps(asdict(PLAN) | {"version": 9}))
    with pytest.raises(ValidationError):
        _dry(ctx)
    assert not ctx.state.exists()


def test_policy_denied_models_and_harnesses_are_honoured(ctx):
    rec = _dry(ctx, settings=Settings(frozenset({"gpt-6-luna", "haiku"}), None, False, 40, {}))
    assert "gpt-6-luna" not in rec.changes[0]["new_text"] and "haiku" not in rec.changes[0]["new_text"]
    with pytest.raises(RouteError, match="policy"):
        _dry(ctx, ("codex",), settings=Settings(frozenset(), frozenset({"claude-code"}), False, 40, {}))


def test_unknown_target_and_no_targets(ctx):
    with pytest.raises(RouteError, match="unknown"):
        _dry(ctx, ("nope",))
    with pytest.raises(RouteError, match="no target"):
        _dry(ctx, ())


def test_two_targets_sharing_agents_md_keep_both_blocks(ctx, capsys):
    rec = _dry(ctx, ("copilot-cli", "codex"))
    agents_md = [c for c in rec.changes if c["path"].endswith("AGENTS.md") and Path(c["path"]).parent == ctx.proj]
    assert len(agents_md) == 1
    text = agents_md[0]["new_text"]
    assert "yardmaster:begin copilot-cli v1" in text and "yardmaster:begin codex v1" in text
    _apply(ctx, rec)
    assert (ctx.proj / "AGENTS.md").read_text(encoding="utf-8").count("yardmaster:begin") == 2
    # running one target again later replaces only its own block
    rec2 = _dry(ctx, ("codex",))
    assert rec2.changes == []  # nothing differs, so nothing is proposed
    assert "up to date" in capsys.readouterr().out


def test_rerun_with_no_change_applies_nothing_new(ctx, capsys):
    _apply(ctx, _dry(ctx))
    capsys.readouterr()
    rec = _dry(ctx)
    assert rec.changes == [] and "up to date" in capsys.readouterr().out
    assert _apply(ctx, rec) == []
