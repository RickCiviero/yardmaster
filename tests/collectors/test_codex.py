from pathlib import Path

import pytest
from synthetic import SINCE, UNTIL, iso, jsonl
from synthetic_codex import codex_home
from yardmaster.collectors import COLLECTORS, CollectorContext
from yardmaster.collectors.codex import collect


@pytest.fixture
def chome(tmp_path):
    return codex_home(tmp_path)


def _ctx(home, **kw):
    return CollectorContext(since=SINCE, until=UNTIL, env={}, platform="linux", roots=[home], **kw)


def _by_id(chats):
    return {c.chat_id: c for c in chats}


def test_registered():
    assert COLLECTORS["codex"] is collect


def test_model_switch_attribution(chome):
    c = _by_id(collect(_ctx(chome)))["cx1"]
    assert c.harness == "codex" and c.credits is None and c.workspace == "C:\\ws\\app"
    assert c.models == {"gpt-5-codex": 200.0, "gpt-5-mini": 60.0}  # output tokens attributed per model at the time


def test_token_totals_use_deltas_and_ignore_duplicates(chome):
    c = _by_id(collect(_ctx(chome)))["cx1"]
    # codex input_tokens includes cached ones: non-cached input = input - cached
    assert sum(t.tokens_in for t in c.turns) == (1000 - 400) + (500 - 300)
    assert sum(t.tokens_cached for t in c.turns) == 400 + 300
    assert sum(t.tokens_out for t in c.turns) == 260


def test_user_prompts_not_injected_context(chome):
    c = _by_id(collect(_ctx(chome)))["cx1"]
    users = [t.text for t in c.turns if t.role == "user"]
    assert users == ["build the parser", "quick follow up"] and c.requests == 2
    assert c.title == "build the parser"
    assert all("environment_context" not in t.text for t in c.turns)


def test_assistant_and_tool_turns(chome):
    c = _by_id(collect(_ctx(chome)))["cx1"]
    asst = [t for t in c.turns if t.role == "assistant" and t.text]
    assert [(t.text, t.model) for t in asst] == [("Parser built", "gpt-5-codex"), ("Sure", "gpt-5-mini")]
    tools = [t.text for t in c.turns if t.role == "tool"]
    assert any(x.startswith("tool_use shell") and "ls" in x for x in tools) and "a\nb" in tools


def test_dir_pruning_includes_tz_edges(chome):
    by = _by_id(collect(_ctx(chome)))
    assert "edge" in by  # 2026/09/03 dir, event at 2026-09-04T00:30Z
    assert "rollout-pruned" not in by and all("must never be read" not in t.text for c in by.values() for t in c.turns)
    assert "rollout-stale" not in by


def test_project_filter(chome):
    assert set(_by_id(collect(_ctx(chome, project=Path("C:\\ws\\other"))))) == {"cx2"}


def test_codex_home_override(tmp_path, chome):
    ctx = CollectorContext(since=SINCE, until=UNTIL, env={"CODEX_HOME": str(chome)}, platform="linux")
    assert "cx1" in _by_id(collect(ctx))
    ctx = CollectorContext(since=SINCE, until=UNTIL, env={"HOME": str(tmp_path)}, platform="linux")
    assert "cx1" in _by_id(collect(ctx))  # default ~/.codex


def test_missing_root_and_hostile_values(tmp_path):
    assert collect(_ctx(tmp_path / "nope")) == []
    rows = [
        {"timestamp": iso(2026, 9, 10), "type": "session_meta", "payload": "str"},
        {"timestamp": iso(2026, 9, 10), "type": "event_msg", "payload": {"type": "user_message", "message": 5}},
        {"timestamp": iso(2026, 9, 10), "type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": "x", "output_tokens": -1, "cached_input_tokens": 10**30}}}},
        {"timestamp": iso(2026, 9, 10), "type": "response_item", "payload": {"type": "message", "role": "assistant",
                                                                             "content": "nope"}},
        {"timestamp": iso(2026, 9, 10), "type": "event_msg", "payload": None},
        {"timestamp": iso(2026, 9, 10), "type": "event_msg", "payload": {"type": "user_message", "message": "ok"}},
    ]
    jsonl(tmp_path / "sessions" / "2026" / "09" / "10" / "rollout-h.jsonl", rows)
    (c,) = collect(_ctx(tmp_path))
    assert [t.text for t in c.turns if t.role == "user"] == ["ok"]
    assert sum(t.tokens_out + t.tokens_in + t.tokens_cached for t in c.turns) == 0
