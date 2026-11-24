"""Synthetic Codex CLI history: <CODEX_HOME>/sessions/YYYY/MM/DD/rollout-*.jsonl.
Shape follows Codex's rollout JSONL (session_meta / turn_context / response_item / event_msg).
NOT verified against a live install (no ~/.codex on the build machine): open owner task."""

from pathlib import Path

from synthetic import iso, jsonl, touch_old


def _line(type_, ts, payload):
    return {"timestamp": ts, "type": type_, "payload": payload}


def _tokens(i, c, o):
    return {"input_tokens": i, "cached_input_tokens": c, "output_tokens": o, "total_tokens": i + o}


def _count(ts, total):
    return _line("event_msg", ts, {"type": "token_count", "info": {"total_token_usage": total}})


def _msg(ts, role, text):
    kind = "output_text" if role == "assistant" else "input_text"
    return _line("response_item", ts, {"type": "message", "role": role, "content": [{"type": kind, "text": text}]})


def codex_home(root: Path) -> Path:
    h = root / ".codex"
    day = h / "sessions" / "2026" / "09" / "10"
    t = lambda m, s=0: iso(2026, 9, 10, 10, m, s)  # noqa: E731
    jsonl(day / "rollout-2026-09-10T10-00-00-cx1.jsonl", [
        _line("session_meta", t(0), {"id": "cx1", "cwd": "C:\\ws\\app"}),
        _line("turn_context", t(0, 1), {"model": "gpt-5-codex", "cwd": "C:\\ws\\app"}),
        _line("event_msg", t(0, 5), {"type": "user_message", "message": "build the parser"}),
        _msg(t(0, 6), "user", "<environment_context>injected, not a user prompt</environment_context>"),
        _msg(t(1), "assistant", "Parser built"),
        _line("response_item", t(1, 1), {"type": "function_call", "name": "shell", "arguments": "{\"cmd\": [\"ls\"]}"}),
        _line("response_item", t(1, 2), {"type": "function_call_output", "output": "a\nb"}),
        _count(t(1, 3), _tokens(1000, 400, 200)),
        _count(t(1, 4), _tokens(1000, 400, 200)),  # duplicate cumulative event
        _line("turn_context", t(4), {"model": "gpt-5-mini"}),
        _line("event_msg", t(5), {"type": "user_message", "message": "quick follow up"}),
        _msg(t(5, 5), "assistant", "Sure"),
        _count(t(5, 6), _tokens(1500, 700, 260)),
    ])
    d22 = h / "sessions" / "2026" / "09" / "22"
    jsonl(d22 / "rollout-2026-09-22T09-00-00-cx2.jsonl", [
        _line("session_meta", iso(2026, 9, 22, 9), {"id": "cx2", "cwd": "C:\\ws\\other"}),
        _line("turn_context", iso(2026, 9, 22, 9), {"model": "gpt-5"}),
        _line("event_msg", iso(2026, 9, 22, 9, 1), {"type": "user_message", "message": "other project"}),
        _count(iso(2026, 9, 22, 9, 2), _tokens(50, 0, 10)),
    ])
    # local-date directory 2026/09/03 holding events that are 2026-09-04 in UTC: inside the range
    jsonl(h / "sessions" / "2026" / "09" / "03" / "rollout-2026-09-03T23-00-00-edge.jsonl", [
        _line("session_meta", iso(2026, 9, 3, 23), {"id": "edge", "cwd": "C:\\ws\\app"}),
        _line("event_msg", iso(2026, 9, 4, 0, 30), {"type": "user_message", "message": "edge of range"}),
    ])
    # two days before the range: pruned by directory name without being read
    jsonl(h / "sessions" / "2026" / "08" / "30" / "rollout-pruned.jsonl", [
        _line("event_msg", iso(2026, 9, 5), {"type": "user_message", "message": "must never be read"}),
    ])
    stale = jsonl(day / "rollout-stale.jsonl", [
        _line("event_msg", t(7), {"type": "user_message", "message": "stale"})])
    touch_old(stale)
    return h
