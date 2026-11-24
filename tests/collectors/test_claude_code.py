from pathlib import Path

import pytest
from synthetic import SINCE, UNTIL, iso, jsonl
from synthetic_claude import claude_home
from yardmaster.collectors import COLLECTORS, CollectorContext
from yardmaster.collectors.claude_code import collect


@pytest.fixture
def chome(tmp_path):
    return claude_home(tmp_path)


def _ctx(home, **kw):
    return CollectorContext(since=SINCE, until=UNTIL, env={}, platform="linux", roots=[home], **kw)


def _by_id(chats):
    return {c.chat_id: c for c in chats}


def test_registered():
    assert COLLECTORS["claude-code"] is collect


def test_tokens_and_models_deduped_by_message_id(chome):
    m = _by_id(collect(_ctx(chome)))["sessMain"]
    assert m.harness == "claude-code" and m.credits is None
    # msg_1 appears on two lines with identical cumulative usage: counted once
    assert m.models == {"claude-opus-5-5": 15.0, "claude-haiku-5-5": 13.0}  # opus 10+5; haiku 7 (msg_3) + 6 (sub)
    asst = [t for t in m.turns if t.role == "assistant"]
    assert sum(t.tokens_out for t in asst) == 28
    assert sum(t.tokens_in for t in asst) == (2 + 100) + 1 + 3 + 4  # input + cache creation
    assert sum(t.tokens_cached for t in asst) == 50


def test_assistant_text_and_model_on_turn(chome):
    m = _by_id(collect(_ctx(chome)))["sessMain"]
    plan = next(t for t in m.turns if t.text == "Plan ready")
    assert plan.model == "claude-opus-5-5" and plan.tokens_out == 10 and plan.ts is not None


def test_tool_use_and_tool_results_are_tool_role(chome):
    m = _by_id(collect(_ctx(chome)))["sessMain"]
    tools = [t.text for t in m.turns if t.role == "tool"]
    assert any(x.startswith("tool_use Bash") and "ls" in x for x in tools)
    assert "file1\nfile2" in tools


def test_requests_count_user_prompts_only(chome):
    m = _by_id(collect(_ctx(chome)))["sessMain"]
    assert m.requests == 2  # two real prompts; not the tool_result, not the sidechain prompt, not the Aug one
    assert [t.text for t in m.turns if t.role == "user"][:1] == ["plan the migration"]


def test_sidechain_and_subagent_files_attributed_to_session(chome):
    by = _by_id(collect(_ctx(chome)))
    texts = [t.text for t in by["sessMain"].turns]
    assert "subagent says hi" in texts and "sub answer" in texts and "sub prompt" in texts
    assert "agent-1" not in by


def test_title_from_ai_title_and_workspace(chome):
    m = _by_id(collect(_ctx(chome)))["sessMain"]
    assert m.title == "Migration planning" and m.workspace == "C:\\ws\\app"


def test_range_filter_by_line_timestamp(chome):
    m = _by_id(collect(_ctx(chome)))["sessMain"]
    texts = [t.text for t in m.turns]
    assert "way before the range" not in texts and "old" not in texts
    assert m.models["claude-opus-5-5"] == 15.0  # the 9999-token Aug message is excluded
    assert m.first.day == 10 and m.last.day == 11


def test_synthetic_model_ignored(chome):
    m = _by_id(collect(_ctx(chome)))["sessMain"]
    assert "<synthetic>" not in m.models


def test_stale_file_skipped_and_project_filter(chome):
    assert "sessStale" not in _by_id(collect(_ctx(chome)))
    assert set(_by_id(collect(_ctx(chome, project=Path("C:\\ws\\other"))))) == {"sessOther"}


def test_claude_config_dir_override(tmp_path, chome):
    ctx = CollectorContext(since=SINCE, until=UNTIL, env={"CLAUDE_CONFIG_DIR": str(chome)}, platform="linux")
    assert "sessMain" in _by_id(collect(ctx))
    ctx = CollectorContext(since=SINCE, until=UNTIL, env={"HOME": str(tmp_path)}, platform="linux")
    assert "sessMain" in _by_id(collect(ctx))  # default ~/.claude


def test_missing_root_and_hostile_values(tmp_path):
    assert collect(_ctx(tmp_path / "nope")) == []
    s = "hostile"
    rows = [
        {"type": "user", "timestamp": iso(2026, 9, 10), "sessionId": s, "message": {"content": 12345}},
        {"type": "user", "timestamp": iso(2026, 9, 10), "sessionId": s, "message": {"content": [None, 3, {"type": 7}]}},
        {"type": "assistant", "timestamp": iso(2026, 9, 10), "message": {"id": "m", "model": "x", "content": "str",
         "usage": {"input_tokens": "9", "output_tokens": -5, "cache_read_input_tokens": float("nan")}}},
        {"type": "assistant", "timestamp": iso(2026, 9, 10), "message": {"id": "m2", "model": "x",
         "content": [{"type": "text", "text": "ok"}], "usage": {"input_tokens": 10**30, "output_tokens": 4}}},
        {"type": "assistant", "timestamp": "garbage", "message": "nope"},
        {"type": "assistant", "timestamp": iso(2026, 9, 10), "message": None},
    ]
    jsonl(tmp_path / "projects" / "p" / "hostile.jsonl", rows)
    (c,) = collect(_ctx(tmp_path))
    out = sum(t.tokens_out for t in c.turns)
    assert out == 4 and all(0 <= t.tokens_in <= 10**9 and t.tokens_cached == 0 for t in c.turns)
