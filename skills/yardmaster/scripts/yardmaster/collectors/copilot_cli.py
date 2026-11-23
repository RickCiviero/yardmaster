"""GitHub Copilot CLI / app: ~/.copilot/session-state/<id>/events.jsonl. Ported from the owner's script."""

import math
import re
from pathlib import Path

from yardmaster.model import Chat, Turn
from yardmaster.safe_io import MAX_FILE, iter_jsonl, read_text
from yardmaster.timeutil import parse_ts

from . import COLLECTORS, CollectorContext, mtime_utc
from .vscode_copilot import _in_project

NANO_PER_CREDIT = 1e9


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _yaml_field(path: Path, field: str) -> str:
    # one-line regex on purpose: no YAML parser in the runtime (stdlib-only, nothing to exploit)
    try:
        for line in read_text(path).splitlines():
            m = re.match(rf"^\s*{re.escape(field)}\s*:\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip("'\"")
    except OSError:
        pass
    return ""


def _local_str(dt) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else ""


def _home(ctx: CollectorContext) -> Path:
    if ctx.roots:
        return Path(ctx.roots[0])
    if ctx.env.get("COPILOT_HOME"):
        return Path(ctx.env["COPILOT_HOME"])
    return Path(ctx.env.get("HOME") or ctx.env.get("USERPROFILE") or Path.home()) / ".copilot"


def collect(ctx: CollectorContext) -> list[Chat]:
    state = _home(ctx) / "session-state"
    chats: list[Chat] = []
    if not state.is_dir():
        return chats
    for d in sorted(state.iterdir()):
        ev = d / "events.jsonl" if d.is_dir() else (d if d.suffix == ".jsonl" else None)
        if ev is None or not ev.exists() or mtime_utc(ev) < ctx.since:
            continue
        if ev.stat().st_size > MAX_FILE:
            ctx.warnings.append(f"skipped oversized file {ev.parent.name}")
            continue
        first = last = snap_ts = None
        in_range = user_msgs = 0
        snap, models, title = None, {}, ""
        turns: list[Turn] = []
        for e in iter_jsonl(ev):
            ts = parse_ts(e.get("timestamp"))
            if ts is None:
                continue
            etype = str(e.get("type", ""))
            data = e.get("data") if isinstance(e.get("data"), dict) else {}
            if ctx.since <= ts < ctx.until:
                in_range += 1
                first = first or ts
                last = ts
                content = data.get("content")
                if etype == "user.message":
                    user_msgs += 1
                    if isinstance(content, str):
                        title = title or " ".join(content.split())[:80]
                        turns.append(Turn("user", content, ts=ts))
                elif etype.startswith("assistant.") and isinstance(content, str):
                    # shortcut: assistant event shape assumed from the user.message one; verify on a live CLI
                    m = data.get("model")
                    turns.append(Turn("assistant", content, model=m if isinstance(m, str) else None, ts=ts))
            if etype == "session.shutdown":
                s = data.get("accountingSnapshot") or {}
                if isinstance(s, dict) and _is_num(s.get("totalNanoAiu")):
                    snap, snap_ts = s, ts
                    mm = data.get("modelMetrics")
                    models = mm if isinstance(mm, dict) else {}
        if not in_range:
            continue
        counted = snap is not None and ctx.since <= snap_ts < ctx.until
        if snap is None:
            note = "no shutdown snapshot (credits unknown)"
        elif not counted:
            note = f"session ended {_local_str(snap_ts)}, outside range: credits not counted here"
        else:
            status = snap.get("aiCreditsStatus", "complete")
            note = "" if status == "complete" else f"aiCreditsStatus={status}"
        is_dir = ev.name == "events.jsonl"
        ws_yaml = ev.parent / "workspace.yaml" if is_dir else None
        cwd = _yaml_field(ws_yaml, "cwd") if ws_yaml and ws_yaml.exists() else ""
        if ctx.project is not None and not (cwd and _in_project(cwd, ctx.project)):
            continue
        chats.append(
            Chat(
                harness="copilot-cli",
                chat_id=ev.parent.name if is_dir else ev.stem,
                workspace=cwd,
                title=title,
                first=first,
                last=last,
                turns=turns,
                requests=user_msgs,
                credits=float(snap["totalNanoAiu"]) / NANO_PER_CREDIT if counted else 0.0,
                models={m: 0.0 for m in models},
                notes=[note] if note else [],
            )
        )
    return chats


COLLECTORS["copilot-cli"] = collect
