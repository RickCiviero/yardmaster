"""Claude Code: <config>/projects/<encoded-cwd>/<session>.jsonl (+ <session>/subagents/*.jsonl).

One API response is written as several lines sharing message.id, each carrying the response's cumulative usage,
so usage is taken once per message id (the max seen), never summed across lines.
"""

import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from yardmaster.model import Chat, Turn
from yardmaster.safe_io import MAX_FILE, iter_jsonl
from yardmaster.timeutil import parse_ts

from . import COLLECTORS, CollectorContext, in_project, mtime_utc

_MIN = datetime.min.replace(tzinfo=UTC)


def _nat(v: object) -> int:
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 10**9
    return int(v) if ok else 0


def _blocks(content) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(c) -> str:
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b["text"] for b in c if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def _root(ctx: CollectorContext) -> Path:
    if ctx.roots:
        return Path(ctx.roots[0])
    if ctx.env.get("CLAUDE_CONFIG_DIR"):
        return Path(ctx.env["CLAUDE_CONFIG_DIR"])
    return Path(ctx.env.get("HOME") or ctx.env.get("USERPROFILE") or Path.home()) / ".claude"


def _session(ctx: CollectorContext, sid: str, files: list[Path]) -> Chat | None:
    if all(mtime_utc(f) < ctx.since for f in files):
        return None
    turns: list[Turn] = []
    by_msg: dict[str, Turn] = {}
    tool_ids: set[str] = set()
    title = cwd = ""
    stamps: list[datetime] = []
    requests = 0
    n = 0
    for f in files:
        try:
            if f.stat().st_size > MAX_FILE:
                ctx.warnings.append(f"skipped oversized file {f.name}")
                continue
        except OSError:
            continue
        in_sub = f.parent.name == "subagents"
        for e in iter_jsonl(f):
            etype = e.get("type")
            if etype == "ai-title" and isinstance(e.get("aiTitle"), str):
                title = e["aiTitle"]
                continue
            if etype not in ("user", "assistant"):
                continue
            if not cwd and isinstance(e.get("cwd"), str):
                cwd = e["cwd"]
            ts = parse_ts(e.get("timestamp"))
            msg = e.get("message")
            if ts is None or not (ctx.since <= ts < ctx.until) or not isinstance(msg, dict):
                continue
            side = in_sub or e.get("isSidechain") is True
            n += 1
            if etype == "user":
                texts, has_result = [], False
                for b in _blocks(msg.get("content")):
                    if b.get("type") == "text" and isinstance(b.get("text"), str):
                        texts.append(b["text"])
                    elif b.get("type") == "tool_result":
                        has_result = True
                        turns.append(Turn("tool", _result_text(b.get("content")), ts=ts))
                if texts:
                    turns.append(Turn("user", "\n".join(texts), ts=ts))
                if not side and not has_result:
                    requests += 1
                stamps.append(ts)
                continue
            model = msg.get("model")
            if not isinstance(model, str) or model.startswith("<"):  # "<synthetic>" = client-side error stub
                continue
            usage = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
            tin = _nat(usage.get("input_tokens")) + _nat(usage.get("cache_creation_input_tokens"))
            tout, tcache = _nat(usage.get("output_tokens")), _nat(usage.get("cache_read_input_tokens"))
            mid = msg["id"] if isinstance(msg.get("id"), str) else f"line-{n}"
            texts = []
            for b in _blocks(msg.get("content")):
                if b.get("type") == "text" and isinstance(b.get("text"), str):
                    texts.append(b["text"])
                elif b.get("type") == "tool_use" and b.get("id") not in tool_ids:
                    tool_ids.add(b.get("id"))
                    args = json.dumps(b.get("input"), ensure_ascii=False, default=str)
                    turns.append(Turn("tool", f"tool_use {b.get('name')} {args}", ts=ts))
            turn = by_msg.get(mid)
            if turn is None:
                turn = by_msg[mid] = Turn("assistant", "", model=model, ts=ts)
                turns.append(turn)
            turn.text = "\n".join(filter(None, [turn.text, *texts]))
            turn.tokens_in, turn.tokens_out = max(turn.tokens_in, tin), max(turn.tokens_out, tout)
            turn.tokens_cached = max(turn.tokens_cached, tcache)
            stamps.append(ts)
    if not stamps:
        return None
    if ctx.project is not None and not (cwd and in_project(cwd, ctx.project)):
        return None
    turns.sort(key=lambda t: t.ts or _MIN)
    models: dict[str, float] = defaultdict(float)
    for t in turns:
        if t.role == "assistant" and t.model:
            models[t.model] += t.tokens_out
    first_user = next((t.text for t in turns if t.role == "user" and t.text), "")
    return Chat(
        harness="claude-code",
        chat_id=sid,
        workspace=cwd,
        title=title or " ".join(first_user.split())[:80],
        first=min(stamps),
        last=max(stamps),
        turns=turns,
        requests=requests,
        credits=None,
        models=dict(models),
        notes=[],
    )


def collect(ctx: CollectorContext) -> list[Chat]:
    projects = _root(ctx) / "projects"
    if not projects.is_dir():
        return []
    chats: list[Chat] = []
    for pdir in sorted(p for p in projects.iterdir() if p.is_dir()):
        for main in sorted(pdir.glob("*.jsonl")):
            sub = pdir / main.stem / "subagents"
            files = [main, *(sorted(sub.glob("*.jsonl")) if sub.is_dir() else [])]
            if chat := _session(ctx, main.stem, files):
                chats.append(chat)
    return chats


COLLECTORS["claude-code"] = collect
