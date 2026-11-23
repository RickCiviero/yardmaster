"""Synthetic, deterministic history trees in each harness's on-disk shape.

Shapes for VS Code / Copilot CLI are derived from the owner's reference script (reference/copilot_chats_to_md.py);
Claude Code / Codex shapes from the harnesses' documented JSONL. They are NOT copies of real chats. Verifying them
against live installs is an open owner task (see docs/wiki/Supported-harnesses.md).
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

SINCE = datetime(2026, 9, 4, tzinfo=UTC)
UNTIL = datetime(2026, 9, 23, tzinfo=UTC)  # inclusive range 2026-09-04 .. 2026-09-22


def ms(y, mo, d, h=10, mi=0) -> int:
    return int(datetime(y, mo, d, h, mi, tzinfo=UTC).timestamp() * 1000)


def iso(y, mo, d, h=10, mi=0, s=0) -> str:
    return datetime(y, mo, d, h, mi, s, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def jsonl(path: Path, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def touch_old(path: Path, y=2026, mo=8, d=1) -> None:
    t = datetime(y, mo, d, tzinfo=UTC).timestamp()
    os.utime(path, (t, t))


def _vs_req(ts, model, credits, text, reply, auto=None):
    r = {"timestamp": ts, "modelId": f"copilot/{model}", "message": {"text": text}, "response": [
        {"value": reply, "supportThemeIcons": False}]}
    if credits is not None:
        r["copilotCredits"] = credits
    if auto:
        r["response"].insert(0, {"kind": "autoModeResolution", "resolved": {"id": auto}})
    return r


def vscode_user(root: Path) -> Path:
    """Returns the `User` dir: <root>/Code/User."""
    u = root / "Code" / "User"
    ws1 = u / "workspaceStorage" / "hash1"
    ws1.mkdir(parents=True)
    (ws1 / "workspace.json").write_text(json.dumps({"folder": "file:///c%3A/ws/Jos%C3%A9/app"}))
    ws2 = u / "workspaceStorage" / "hash2"
    ws2.mkdir(parents=True)
    (ws2 / "workspace.json").write_text(json.dumps({"folder": "file:///c%3A/ws/other"}))

    # A: change log using every op kind
    r1 = _vs_req(ms(2026, 9, 10), "claude-opus-4.5", None, "plan the migration", "Here is the plan")
    r2 = _vs_req(ms(2026, 9, 10, 11), "gpt-5", 0.5, "fix the failing test", "Fixed")
    jsonl(ws1 / "chatSessions" / "sessA.jsonl", [
        {"kind": 0, "v": {"version": 3, "requests": [], "scratch": 1}},
        {"kind": 2, "k": ["requests"], "v": [r1, r2]},
        {"kind": 1, "k": ["requests", 0, "copilotCredits"], "v": 1.5},
        {"kind": 1, "k": ["customTitle"], "v": "Migration planning"},
        {"kind": 3, "k": ["scratch"]},
        {"kind": 1, "k": ["requests", 99, "x"], "v": 1},  # bad index: ignored
        {"kind": 7, "k": [], "v": None},  # unknown kind: ignored
        "not a dict",
    ])
    tr = ws1 / "GitHub.copilot-chat" / "transcripts"
    tr.mkdir(parents=True)
    jsonl(tr / "sessA.jsonl", [{"type": "note", "text": "transcript line"}])

    # B: legacy .json with one request lacking credits and one outside the range
    (ws1 / "chatSessions" / "sessB.json").write_text(json.dumps({"version": 3, "requests": [
        _vs_req(ms(2026, 9, 15), "gpt-5", 0.25, "where is the router config?", "In .agents/"),
        _vs_req(ms(2026, 9, 16), "gpt-5", None, "and the schema?", "In schema.py"),
        _vs_req(ms(2026, 8, 20), "gpt-5", 9.0, "old question", "old answer"),
    ]}))
    # C: no workspace, auto mode
    jsonl(u / "globalStorage" / "emptyWindowChatSessions" / "sessC.jsonl", [
        {"kind": 0, "v": {"requests": [
            _vs_req(ms(2026, 9, 12), "auto", 0.1, "quick question", "quick answer", auto="gpt-5-mini")]}}])
    # D: all requests outside the range; E: file untouched since before the range
    jsonl(ws2 / "chatSessions" / "sessD.jsonl", [
        {"kind": 0, "v": {"requests": [_vs_req(ms(2026, 8, 2), "gpt-5", 3.0, "q", "a")]}}])
    e = jsonl(ws2 / "chatSessions" / "sessE.jsonl", [
        {"kind": 0, "v": {"requests": [_vs_req(ms(2026, 9, 10), "gpt-5", 3.0, "q", "a")]}}])
    touch_old(e)
    return u


def _cli_events(user_ts: list[str], shutdown: tuple[str, float, str] | None, models=("gpt-5",)):
    rows = [{"type": "session.start", "timestamp": user_ts[0], "data": {}}]
    for i, t in enumerate(user_ts):
        rows.append({"type": "user.message", "timestamp": t, "data": {"content": f"cli question {i}"}})
        rows.append({"type": "assistant.message", "timestamp": t, "data": {"content": f"cli answer {i}",
                                                                          "model": models[0]}})
    if shutdown:
        ts, nano, status = shutdown
        rows.append({"type": "session.shutdown", "timestamp": ts, "data": {
            "accountingSnapshot": {"totalNanoAiu": nano, "aiCreditsStatus": status},
            "modelMetrics": {m: {"requests": 1} for m in models}}})
    return rows


def copilot_home(root: Path) -> Path:
    h = root / ".copilot"
    ss = h / "session-state"

    def session(name, rows, cwd="C:\ws\app"):
        jsonl(ss / name / "events.jsonl", rows)
        (ss / name / "workspace.yaml").write_text(f"id: {name}\ncwd: '{cwd}'\n")

    session("cliOk", _cli_events([iso(2026, 9, 10), iso(2026, 9, 10, 11)], (iso(2026, 9, 10, 12), 2.5e9, "complete")))
    session("cliLate", _cli_events([iso(2026, 9, 21)], (iso(2026, 10, 2), 7e9, "complete")), cwd="C:\ws\other")
    session("cliNoShutdown", _cli_events([iso(2026, 9, 11)], None))
    session("cliPartial", _cli_events([iso(2026, 9, 12)], (iso(2026, 9, 12, 12), 1e9, "partial"), models=("gpt-5", "o4")))
    jsonl(ss / "bare.jsonl", _cli_events([iso(2026, 9, 13)], (iso(2026, 9, 13, 12), 3e9, "complete")))
    session("cliOutside", _cli_events([iso(2026, 8, 13)], (iso(2026, 8, 13, 12), 9e9, "complete")))
    stale = ss / "cliStale"
    jsonl(stale / "events.jsonl", _cli_events([iso(2026, 9, 10)], (iso(2026, 9, 10, 12), 9e9, "complete")))
    touch_old(stale / "events.jsonl")
    return h
