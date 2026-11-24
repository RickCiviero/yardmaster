"""One redacted Markdown archive of a range of chats (the owner's old copilot_chats_to_md.py output, made safe)."""

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .model import Chat
from .redact import redact
from .timeutil import DateRange


def _fence(text: str) -> str:
    return "`" * max(3, max((len(m) for m in re.findall(r"`+", text)), default=0) + 1)


def _anchor(text: str) -> str:
    return re.sub(r"[^\w\- ]", "", text.lower()).strip().replace(" ", "-")


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _local(dt) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else ""


def _in_git_repo(d: Path) -> bool:
    return any((p / ".git").exists() for p in [d.resolve(), *d.resolve().parents])


def export_md(chats: list[Chat], r: DateRange, out_dir: Path, *, pii: bool, overwrite: bool = False, force: bool = False) -> Path:
    out_dir = Path(out_dir)
    if not force and _in_git_repo(out_dir):
        raise PermissionError(f"{out_dir} is inside a git repository, where chat history could get committed; use --force to override")
    path = out_dir / f"{r.name}.md"
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists. Use --overwrite to replace it.")

    def red(s: str) -> str:
        return redact(str(s), pii=pii)[0]

    out = [f"# AI chats {r.start} .. {r.end}", "",
           f"Generated {datetime.now():%Y-%m-%d %H:%M}. Range in local time, both ends inclusive. Secrets are redacted.", ""]
    if not chats:
        out.append("No chats in this range.")
    else:
        chats = sorted(chats, key=lambda c: c.first)
        out += ["## Summary", "", "| Harness | Chats | Requests | Credits |", "|---|---:|---:|---:|"]
        for h in sorted({c.harness for c in chats}):
            cs = [c for c in chats if c.harness == h]
            out.append(f"| {h} | {len(cs)} | {sum(c.requests for c in cs)} | {sum(c.credits or 0 for c in cs):,.2f} |")
        credits_by, tokens_by = defaultdict(float), defaultdict(float)
        for c in chats:
            for m, v in c.models.items():
                (credits_by if c.credits is not None else tokens_by)[red(m)] += v
        out += ["", "## Credits and tokens by model", "", "| Model | Credits | Tokens out |", "|---|---:|---:|"]
        for m in sorted(set(credits_by) | set(tokens_by), key=lambda m: -(credits_by[m] + tokens_by[m])):
            out.append(f"| {_cell(m)} | {credits_by[m]:,.2f} | {tokens_by[m]:,.0f} |")
        out += ["", "## Index", "", "| # | Harness | First activity | Last activity | Workspace | Title | Requests | Credits | Models |",
                "|---:|---|---|---|---|---|---:|---:|---|"]
        for i, c in enumerate(chats, 1):
            out.append(f"| [{i}](#{_anchor(f'{i}. {c.harness} {c.chat_id}')}) | {c.harness} | {_local(c.first)} | {_local(c.last)} | "
                       f"{_cell(red(c.workspace))} | {_cell(red(c.title))} | {c.requests} | {(c.credits or 0):,.2f} | "
                       f"{_cell(', '.join(red(m) for m in c.models))} |")
        out += ["", "---", ""]
        for i, c in enumerate(chats, 1):
            out += [f"## {i}. {c.harness} {c.chat_id}", "", f"- **Workspace:** {red(c.workspace) or '-'}"]
            if c.title:
                out.append(f"- **Title:** {red(c.title)}")
            out.append(f"- **Activity:** {_local(c.first)} .. {_local(c.last)}")
            spend = (f"**Credits:** {c.credits:,.4f}" if c.credits is not None else
                     f"**Tokens:** in={sum(t.tokens_in for t in c.turns)} out={sum(t.tokens_out for t in c.turns)} "
                     f"cached={sum(t.tokens_cached for t in c.turns)}")
            out.append(f"- **Requests:** {c.requests}  |  {spend}")
            if c.models:
                out.append(f"- **Models:** {', '.join(red(m) for m in c.models)}")
            out += [f"- **Note:** {red(n)}" for n in c.notes] + [""]
            for t in c.turns:
                text = red(t.text)
                if not text.strip():
                    continue
                f = _fence(text)
                label = t.role + (f" {red(t.model)}" if t.model else "")
                out += [f"**{label}**", "", f"{f}text", text.rstrip("\n"), f, ""]
            out += ["---", ""]
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    return path
