"""Synthetic Claude Code history. Shape verified (structure only) against a real ~/.claude/projects tree,
Claude Code 2.1.311: type/timestamp/sessionId/cwd/isSidechain on each line, message.model + message.usage on
assistant lines, `ai-title` lines, and one API response split across several lines sharing message.id."""

from pathlib import Path

from synthetic import iso, jsonl, touch_old


def _cc(type_, ts, session, cwd="C:\\ws\\app", sidechain=False, **msg):
    e = {"type": type_, "timestamp": ts, "sessionId": session, "cwd": cwd, "isSidechain": sidechain, "uuid": ts}
    if msg:
        e["message"] = msg
    return e


def _usage(i, o, cr=0, cc=0):
    return {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cc}


def claude_home(root: Path) -> Path:
    h = root / ".claude"
    proj = h / "projects" / "C--ws-app"
    s = "sessMain"
    jsonl(proj / f"{s}.jsonl", [
        _cc("user", iso(2026, 9, 10), s, role="user", content=[{"type": "text", "text": "plan the migration"}]),
        _cc("assistant", iso(2026, 9, 10, 10, 1), s, id="msg_1", model="claude-opus-5-5", role="assistant",
            content=[{"type": "thinking", "thinking": "", "signature": "x"}], usage=_usage(2, 10, 50, 100)),
        _cc("assistant", iso(2026, 9, 10, 10, 2), s, id="msg_1", model="claude-opus-5-5", role="assistant",
            content=[{"type": "text", "text": "Plan ready"}], usage=_usage(2, 10, 50, 100)),  # same message, split line
        _cc("assistant", iso(2026, 9, 10, 10, 3), s, id="msg_2", model="claude-opus-5-5", role="assistant",
            content=[{"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "ls"}}],
            usage=_usage(1, 5)),
        _cc("user", iso(2026, 9, 10, 10, 4), s, role="user",
            content=[{"type": "tool_result", "tool_use_id": "tu1", "content": "file1\nfile2"}]),
        _cc("assistant", iso(2026, 9, 10, 10, 5), s, sidechain=True, id="msg_3", model="claude-haiku-5-5",
            role="assistant", content=[{"type": "text", "text": "subagent says hi"}], usage=_usage(3, 7)),
        _cc("user", iso(2026, 9, 11), s, role="user", content="second prompt as plain string"),
        _cc("assistant", iso(2026, 9, 11, 10, 1), s, id="msg_4", model="<synthetic>", role="assistant",
            content=[{"type": "text", "text": "API error"}], usage=_usage(0, 0)),
        {"type": "ai-title", "aiTitle": "Migration planning", "sessionId": s},
        {"type": "queue-operation", "operation": "enqueue", "timestamp": iso(2026, 9, 10)},
        _cc("user", iso(2026, 8, 1), s, role="user", content="way before the range"),
        _cc("assistant", iso(2026, 8, 1, 10, 1), s, id="msg_old", model="claude-opus-5-5", role="assistant",
            content=[{"type": "text", "text": "old"}], usage=_usage(9, 9999)),
    ])
    jsonl(proj / s / "subagents" / "agent-1.jsonl", [
        _cc("user", iso(2026, 9, 10, 10, 6), s, sidechain=True, role="user", content="sub prompt"),
        _cc("assistant", iso(2026, 9, 10, 10, 7), s, sidechain=True, id="msg_5", model="claude-haiku-5-5",
            role="assistant", content=[{"type": "text", "text": "sub answer"}], usage=_usage(4, 6)),
    ])
    other = h / "projects" / "C--ws-other"
    jsonl(other / "sessOther.jsonl", [
        _cc("user", iso(2026, 9, 20), "sessOther", cwd="C:\\ws\\other", role="user", content="other project"),
        _cc("assistant", iso(2026, 9, 20, 10, 1), "sessOther", cwd="C:\\ws\\other", id="msg_9",
            model="claude-sonnet-5-5", role="assistant", content=[{"type": "text", "text": "ok"}],
            usage=_usage(5, 5)),
    ])
    stale = jsonl(other / "sessStale.jsonl", [_cc("user", iso(2026, 9, 10), "sessStale", role="user", content="stale")])
    touch_old(stale)
    return h
