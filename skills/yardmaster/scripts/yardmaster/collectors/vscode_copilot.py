"""GitHub Copilot in VS Code / VS Code Insiders. Ported from the owner's copilot_chats_to_md.py."""

import math
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse

from yardmaster.model import Chat, Turn
from yardmaster.paths import vscode_user_dirs
from yardmaster.safe_io import MAX_FILE, iter_jsonl, load_json
from yardmaster.timeutil import parse_ts

from . import COLLECTORS, CollectorContext, in_project, mtime_utc, skip_linked


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def replay(path: Path):
    """Rebuild a session from a chatSessions change log (kind 0 initial, 1 set at k, 2 push/splice at k, 3 delete)."""
    state = None
    for op in iter_jsonl(path):
        kind, k, v = op.get("kind"), op.get("k") or [], op.get("v")
        if kind == 0:
            state = v
            continue
        if state is None:
            continue
        try:
            parent = state
            for key in k[:-1]:
                parent = parent[key]
            last = k[-1] if k else None
            if kind == 1:
                if last is None:
                    state = v
                else:
                    parent[last] = v
            elif kind == 2:
                tgt = parent[last] if last is not None else parent
                if isinstance(tgt, list):
                    if _is_num(op.get("i")):
                        del tgt[int(op["i"]) :]
                    tgt.extend(v if isinstance(v, list) else [v])
            elif kind == 3 and last is not None:
                if isinstance(parent, list) and _is_num(last) and last < len(parent):
                    parent.pop(last)
                elif isinstance(parent, dict):
                    parent.pop(last, None)
        except (KeyError, IndexError, TypeError, OverflowError, ValueError):
            continue
    return state


def _load_session(path: Path):
    return replay(path) if path.suffix == ".jsonl" else load_json(path)


def _workspace_path(ws_dir: Path) -> str:
    data = load_json(ws_dir / "workspace.json")
    if not isinstance(data, dict):
        return ""
    uri = data.get("folder") or data.get("workspace") or ""
    if not isinstance(uri, str):
        return ""
    if uri.startswith("file://"):
        p = unquote(urlparse(uri).path)
        return p[1:] if re.match(r"^/[A-Za-z]:", p) else p
    return unquote(uri)


def _model_of(req: dict) -> str:
    for part in req.get("response") or []:
        if isinstance(part, dict) and part.get("kind") == "autoModeResolution":
            return "auto -> " + str((part.get("resolved") or {}).get("id") or "?")
    return str(req.get("modelId") or "?").replace("copilot/", "")


def _title_of(sess: dict, reqs: list[dict]) -> str:
    t = sess.get("customTitle") or sess.get("title")
    if t:
        return str(t)
    for r in reqs:
        msg = r.get("message") or {}
        text = msg.get("text") if isinstance(msg, dict) else None
        if text:
            return " ".join(str(text).split())[:80]
    return ""


def _part_text(p) -> str | None:
    # shortcut: best-effort text extraction (plain value / markdownContent); tool parts are skipped.
    # Verify against a live VS Code before relying on assistant text (open owner task).
    if not isinstance(p, dict):
        return None
    v = p.get("value")
    if isinstance(v, str):
        return v
    c = p.get("content")
    if isinstance(c, dict) and isinstance(c.get("value"), str):
        return c["value"]
    return None


def _turns(ts, r: dict) -> list[Turn]:
    out: list[Turn] = []
    msg = r.get("message")
    text = msg.get("text") if isinstance(msg, dict) else None
    if isinstance(text, str) and text:
        out.append(Turn("user", text, ts=ts))
    parts = [t for t in map(_part_text, r.get("response") or []) if t]
    if parts:
        out.append(Turn("assistant", "\n".join(parts), model=_model_of(r), ts=ts))
    return out


def collect(ctx: CollectorContext) -> list[Chat]:
    user_dirs = [Path(r) for r in ctx.roots] if ctx.roots else vscode_user_dirs(ctx.env, ctx.platform)
    chats: list[Chat] = []
    for ud in user_dirs:
        sources: list[tuple[Path, Path | None]] = []
        for ws in sorted((ud / "workspaceStorage").glob("*")):
            cs = ws / "chatSessions"
            if cs.is_dir():
                sources += [(f, ws) for f in sorted(cs.iterdir()) if f.suffix in (".json", ".jsonl")]
        empty = ud / "globalStorage" / "emptyWindowChatSessions"
        if empty.is_dir():
            sources += [(f, None) for f in sorted(empty.iterdir()) if f.suffix in (".json", ".jsonl")]

        sources = [(f, ws) for f, ws in sources if not skip_linked(ctx, f, ud)]
        for f, ws in sources:
            try:
                if f.stat().st_size > MAX_FILE:
                    ctx.warnings.append(f"skipped oversized file {f.name}")
                    continue
            except OSError:
                continue
            if mtime_utc(f) < ctx.since:  # untouched since the range started: no activity in it
                continue
            sess = _load_session(f)
            if not isinstance(sess, dict) or not isinstance(sess.get("requests"), list):
                continue
            in_range = []
            for r in sess["requests"]:
                if isinstance(r, dict):
                    ts = parse_ts(r.get("timestamp"))
                    if ts and ctx.since <= ts < ctx.until:
                        in_range.append((ts, r))
            if not in_range:
                continue
            workspace = (_workspace_path(ws) or ws.name) if ws else "<no folder>"
            if ctx.project is not None and not in_project(workspace, ctx.project):
                continue

            credits, missing, per_model = 0.0, 0, defaultdict(float)
            turns: list[Turn] = []
            for ts, r in in_range:
                c = r.get("copilotCredits")
                if _is_num(c) and math.isfinite(c):
                    credits += c
                    per_model[_model_of(r)] += c
                else:
                    missing += 1
                turns += _turns(ts, r)
            notes = []
            if missing:
                notes.append(f"{missing} requests without credits")
            outside = len(sess["requests"]) - len(in_range)
            if outside > 0:
                notes.append(f"file also contains {outside} requests outside range")
            stamps = [t for t, _ in in_range]
            chats.append(
                Chat(
                    harness="vscode-copilot",
                    chat_id=f.stem,
                    workspace=workspace,
                    title=_title_of(sess, [r for _, r in in_range]),
                    first=min(stamps),
                    last=max(stamps),
                    turns=turns,
                    requests=len(in_range),
                    credits=credits,
                    models=dict(per_model),
                    notes=notes,
                )
            )
    return chats


COLLECTORS["vscode-copilot"] = collect
