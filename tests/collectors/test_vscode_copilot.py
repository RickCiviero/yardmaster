import importlib.util
from pathlib import Path

import pytest
from synthetic import SINCE, UNTIL, vscode_user
from yardmaster.collectors import COLLECTORS, CollectorContext
from yardmaster.collectors.vscode_copilot import collect

REF = Path(__file__).resolve().parents[2] / "reference" / "copilot_chats_to_md.py"


def _ctx(user, **kw):
    return CollectorContext(since=SINCE, until=UNTIL, env={}, platform="linux", roots=[user], **kw)


@pytest.fixture
def user(tmp_path):
    return vscode_user(tmp_path)


def _reference():
    spec = importlib.util.spec_from_file_location("ym_reference", REF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registered():
    assert COLLECTORS["vscode-copilot"] is collect


def test_parity_with_reference(user):
    ref = _reference().collect_vscode([user], SINCE, UNTIL)
    ours = collect(_ctx(user))
    want = {c["id"]: (c["requests"], c["credits"], c["models"], c["note"], c["workspace"], c["title"]) for c in ref}
    got = {c.chat_id: (c.requests, c.credits, c.models, "; ".join(c.notes), c.workspace, c.title) for c in ours}
    assert got.keys() == want.keys() == {"sessA", "sessB", "sessC"}
    for cid in want:
        g, w = got[cid], want[cid]
        assert g[0] == w[0] and g[1] == pytest.approx(w[1], abs=1e-9)
        assert g[2] == pytest.approx(w[2]) and g[3:] == w[3:], cid


def test_replay_all_op_kinds_and_values(user):
    a = {c.chat_id: c for c in collect(_ctx(user))}["sessA"]
    assert a.requests == 2 and a.credits == pytest.approx(2.0)  # 1.5 set by kind 1, plus 0.5
    assert a.models == {"claude-opus-4.5": 1.5, "gpt-5": 0.5}
    assert a.title == "Migration planning" and a.harness == "vscode-copilot"
    assert [t.role for t in a.turns] == ["user", "assistant", "user", "assistant"]
    assert a.turns[0].text == "plan the migration" and a.turns[1].text == "Here is the plan"
    assert a.turns[1].model == "claude-opus-4.5" and a.turns[0].ts is not None
    assert a.first < a.last


def test_missing_credits_and_outside_range_notes(user):
    b = {c.chat_id: c for c in collect(_ctx(user))}["sessB"]
    assert b.requests == 2 and b.credits == pytest.approx(0.25)
    assert "1 requests without credits" in b.notes
    assert any("1 requests outside range" in n for n in b.notes)


def test_auto_model_label_and_no_workspace(user):
    c = {c.chat_id: c for c in collect(_ctx(user))}["sessC"]
    assert list(c.models) == ["auto -> gpt-5-mini"] and c.workspace == "<no folder>"


def test_workspace_path_decoded_with_unicode(user):
    a = {c.chat_id: c for c in collect(_ctx(user))}["sessA"]
    assert a.workspace.replace("\\", "/") == "c:/ws/José/app"


def test_project_filter(user):
    got = {c.chat_id for c in collect(_ctx(user, project=Path("c:/ws/José/app")))}
    assert got == {"sessA", "sessB"}


def test_mtime_older_than_since_skipped(user):
    assert "sessE" not in {c.chat_id for c in collect(_ctx(user))}


def test_vscode_unicode_user_dir(tmp_path):
    u = vscode_user(tmp_path / "José Ñ")
    assert {c.chat_id for c in collect(_ctx(u))} == {"sessA", "sessB", "sessC"}


def test_default_roots_come_from_env(tmp_path):
    vscode_user(tmp_path / "xdg")
    ctx = CollectorContext(
        since=SINCE, until=UNTIL, env={"XDG_CONFIG_HOME": str(tmp_path / "xdg"), "HOME": str(tmp_path)},
        platform="linux",
    )
    assert {c.chat_id for c in collect(ctx)} == {"sessA", "sessB", "sessC"}


def test_hostile_session_files_do_not_crash(user):
    cs = next((user / "workspaceStorage" / "hash1" / "chatSessions").parent.iterdir()).parent
    (cs / "bad1.jsonl").write_bytes(b"\xff\xfe{nope\n" + b"[" * 50000 + b"\n")
    (cs / "bad2.json").write_text("[1,2,3]")
    (cs / "bad3.jsonl").write_text('{"kind": 1, "k": ["requests"], "v": []}\n')  # no kind 0 first
    assert {c.chat_id for c in collect(_ctx(user))} == {"sessA", "sessB", "sessC"}
