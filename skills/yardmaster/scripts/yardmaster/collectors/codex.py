"""OpenAI Codex CLI / IDE: <CODEX_HOME>/sessions/YYYY/MM/DD/rollout-*.jsonl.

Token usage comes from cumulative `token_count` events: each is turned into a delta against the previous total, so
repeated events cost nothing, and the delta is billed to the model that was active (`turn_context`) at the time.
Codex's input_tokens INCLUDES cached tokens, so non-cached input = input - cached.
"""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from yardmaster.model import Chat, Turn
from yardmaster.safe_io import MAX_FILE, iter_jsonl
from yardmaster.timeutil import parse_ts

from . import COLLECTORS, CollectorContext, in_project, mtime_utc, nat

_MIN = datetime.min.replace(tzinfo=UTC)


def _root(ctx: CollectorContext) -> Path:
    if ctx.roots:
        return Path(ctx.roots[0])
    if ctx.env.get("CODEX_HOME"):
        return Path(ctx.env["CODEX_HOME"])
    return Path(ctx.env.get("HOME") or ctx.env.get("USERPROFILE") or Path.home()) / ".codex"


def _dir_date(rel: tuple[str, ...]) -> date | None:
    try:
        return date(int(rel[0]), int(rel[1]), int(rel[2]))
    except (ValueError, IndexError):
        return None


def _text_blocks(content) -> str:
    if not isinstance(content, list):
        return ""
    return "\n".join(b["text"] for b in content if isinstance(b, dict) and isinstance(b.get("text"), str))


def _session(ctx: CollectorContext, f: Path) -> Chat | None:
    turns: list[Turn] = []
    stamps: list[datetime] = []
    sid, cwd, model, title = f.stem, "", "", ""
    prev = {"i": 0, "c": 0, "o": 0}
    requests = 0
    for e in iter_jsonl(f):
        payload = e.get("payload")
        if not isinstance(payload, dict):
            continue
        etype, ptype = e.get("type"), payload.get("type")
        if etype == "session_meta":
            sid = payload["id"] if isinstance(payload.get("id"), str) else sid
            cwd = payload["cwd"] if isinstance(payload.get("cwd"), str) else cwd
            continue
        if etype == "turn_context":
            model = payload["model"] if isinstance(payload.get("model"), str) else model
            cwd = cwd or (payload["cwd"] if isinstance(payload.get("cwd"), str) else "")
            continue
        ts = parse_ts(e.get("timestamp"))
        usage = (payload.get("info") or {}).get("total_token_usage") if ptype == "token_count" else None
        if isinstance(usage, dict):  # deltas are computed over ALL events so out-of-range ones don't leak in
            cur = {
                "i": nat(usage.get("input_tokens")),
                "c": nat(usage.get("cached_input_tokens")),
                "o": nat(usage.get("output_tokens")),
            }
            d = {k: max(0, cur[k] - prev[k]) for k in cur}
            prev = cur
            if ts and ctx.since <= ts < ctx.until and any(d.values()):
                turns.append(Turn("assistant", "", model=model or None, ts=ts, tokens_in=max(0, d["i"] - d["c"]),
                                  tokens_cached=d["c"], tokens_out=d["o"]))
                stamps.append(ts)
            continue
        if ts is None or not (ctx.since <= ts < ctx.until):
            continue
        if etype == "event_msg" and ptype == "user_message" and isinstance(payload.get("message"), str):
            turns.append(Turn("user", payload["message"], ts=ts))
            title = title or " ".join(payload["message"].split())[:80]
            requests += 1
            stamps.append(ts)
        elif etype == "response_item":
            if ptype == "message" and payload.get("role") == "assistant":
                if text := _text_blocks(payload.get("content")):
                    turns.append(Turn("assistant", text, model=model or None, ts=ts))
                    stamps.append(ts)
            elif ptype == "function_call":
                turns.append(Turn("tool", f"tool_use {payload.get('name')} {payload.get('arguments')}", ts=ts))
                stamps.append(ts)
            elif ptype == "function_call_output" and isinstance(payload.get("output"), str):
                turns.append(Turn("tool", payload["output"], ts=ts))
                stamps.append(ts)
    if not stamps or (ctx.project is not None and not (cwd and in_project(cwd, ctx.project))):
        return None
    models: dict[str, float] = defaultdict(float)
    for t in turns:
        if t.role == "assistant" and t.model:
            models[t.model] += t.tokens_out
    return Chat("codex", sid, cwd, title, min(stamps), max(stamps), turns, requests, None, dict(models), [])


def collect(ctx: CollectorContext) -> list[Chat]:
    sessions = _root(ctx) / "sessions"
    if not sessions.is_dir():
        return []
    lo, hi = (ctx.since - timedelta(days=1)).date(), (ctx.until + timedelta(days=1)).date()  # local-date dirs vs UTC
    chats: list[Chat] = []
    for f in sorted(sessions.rglob("rollout-*.jsonl")):
        d = _dir_date(f.relative_to(sessions).parts)
        if (d is not None and not (lo <= d <= hi)) or mtime_utc(f) < ctx.since:
            continue
        try:
            if f.stat().st_size > MAX_FILE:
                ctx.warnings.append(f"skipped oversized file {f.name}")
                continue
        except OSError:
            continue
        if chat := _session(ctx, f):
            chats.append(chat)
    return chats


COLLECTORS["codex"] = collect
