#!/usr/bin/env python3
"""
copilot_chats_to_md.py
Write ONE Markdown file containing every GitHub Copilot chat with activity in a date
range:
an index table, a credit summary, and the ENTIRE raw content of every chat file.

Sources
  VS Code    : %APPDATA%/Code/User/workspaceStorage/<hash>/chatSessions/<id>.jsonl
               (+ GitHub.copilot-chat/transcripts/<id>.jsonl, if present)
               %APPDATA%/Code/User/globalStorage/emptyWindowChatSessions/<id>.jsonl
  CLI / app  : ~/.copilot/session-state/<id>/events.jsonl + workspace.yaml
               (--full: every text file in the session folder)

Range (local time, both ends inclusive)
  --current              1st of this month .. today   -> 2026-11.md
  --last                 whole previous month         -> 2026-10.md
  --from D [--to D]      D .. D (default --to: today) -> 2026-09-04_2026-09-22.md

Credits
  VS Code    : sum of "copilotCredits" of the requests whose timestamp is in the range
               (exact).
  CLI / app  : accountingSnapshot.totalNanoAiu / 1e9 of the LAST session.shutdown event,
               counted if that shutdown falls in the range (session total, cannot be split
               by day).

Usage
  python copilot_chats_to_md.py --current
  python copilot_chats_to_md.py --last --out D:\\copilot_archive
  python copilot_chats_to_md.py --from 2026-09-04 --to 2026-09-22 --overwrite
Standard library only.

NOTE (Yardmaster): transcribed from the owner's scanned printout as the behavioural
reference for the Yardmaster collectors. Not shipped. OCR-level typos may exist; the
logic is what matters.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

NANO_PER_CREDIT = 1e9
TEXT_SUFFIXES = {".jsonl", ".json", ".yaml", ".yml", ".md", ".txt", ".log", ".py", ".ps1",
                 ".cs", ".cpp", ".h", ".toml", ".ini", ".csv", ".xml", ".html"}


# ===================================================================== helpers
def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def parse_ts(v):
    """Epoch ms / epoch s / ISO string -> aware UTC datetime, or None."""
    if is_num(v):
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
    if isinstance(v, str) and v:
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def iter_jsonl(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass
    except OSError:
        return


def mtime_utc(p):
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.min.replace(tzinfo=timezone.utc)


def local_str(dt):
    return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else ""


def md_cell(s):
    """Make a string safe for a Markdown table cell."""
    return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def anchor(text):
    """GitHub-style heading anchor."""
    a = re.sub(r"[^\w\- ]", "", text.lower()).strip().replace(" ", "-")
    return a


# ======================================================================= range
def resolve_range(args):
    """Return (start_date, end_date_inclusive, name)."""
    today = date.today()
    if args.current:
        start = today.replace(day=1)
        return start, today, start.strftime("%Y-%m")
    if args.last:
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
        return start, end, start.strftime("%Y-%m")
    start = datetime.strptime(args.date_from, "%Y-%m-%d").date()
    end = datetime.strptime(args.date_to, "%Y-%m-%d").date() if args.date_to else today
    if end < start:
        sys.exit(f"--to ({end}) is before --from ({start})")
    return start, end, f"{start:%Y-%m-%d}_{end:%Y-%m-%d}"


def to_utc_bounds(start, end):
    """Inclusive local dates -> [since, until) in UTC."""
    since = datetime(start.year, start.month, start.day).astimezone().astimezone(timezone.utc)
    nxt = end + timedelta(days=1)
    until = datetime(nxt.year, nxt.month, nxt.day).astimezone().astimezone(timezone.utc)
    return since, until


# ===================================================================== VS Code
def replay(path):
    """Rebuild a session object from a chatSessions change log
    (kind 0 = initial, 1 = set at k, 2 = push/splice at k, 3 = delete)."""
    state = None
    for op in iter_jsonl(path):
        if not isinstance(op, dict):
            continue
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
                    if is_num(op.get("i")):
                        del tgt[int(op["i"]):]
                    tgt.extend(v if isinstance(v, list) else [v])
            elif kind == 3 and last is not None:
                if isinstance(parent, list) and is_num(last) and last < len(parent):
                    parent.pop(last)
                elif isinstance(parent, dict):
                    parent.pop(last, None)
        except (KeyError, IndexError, TypeError):
            continue
    return state


def load_session(path):
    if path.suffix == ".jsonl":
        return replay(path)
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None


def vscode_user_dirs(explicit):
    if explicit:
        return [Path(p) for p in explicit]
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return [base / f / "User" for f in ("Code", "Code - Insiders") if (base / f / "User").is_dir()]


def workspace_path(ws_dir):
    try:
        data = json.loads((ws_dir / "workspace.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    uri = data.get("folder") or data.get("workspace") or ""
    if uri.startswith("file://"):
        p = unquote(urlparse(uri).path)
        return p[1:] if re.match(r"^/[A-Za-z]:", p) else p
    return unquote(uri)


def model_of(req):
    for part in req.get("response") or []:
        if isinstance(part, dict) and part.get("kind") == "autoModeResolution":
            return "auto -> " + str((part.get("resolved") or {}).get("id") or "?")
    return str(req.get("modelId") or "?").replace("copilot/", "")


def title_of(sess, reqs):
    t = sess.get("customTitle") or sess.get("title")
    if t:
        return str(t)
    for r in reqs:
        msg = r.get("message") or {}
        text = msg.get("text") if isinstance(msg, dict) else None
        if text:
            return " ".join(str(text).split())[:80]
    return ""


def collect_vscode(user_dirs, since, until):
    chats = []
    for ud in user_dirs:
        sources = []  # (file, workspace_dir_or_None)
        for ws in (ud / "workspaceStorage").glob("*"):
            cs = ws / "chatSessions"
            if cs.is_dir():
                sources += [(f, ws) for f in cs.iterdir() if f.suffix in (".json", ".jsonl")]
        empty = ud / "globalStorage" / "emptyWindowChatSessions"
        if empty.is_dir():
            sources += [(f, None) for f in empty.iterdir() if f.suffix in (".json", ".jsonl")]

        for f, ws in sources:
            if mtime_utc(f) < since:  # untouched since the start: no activity in range
                continue
            sess = load_session(f)
            if not isinstance(sess, dict):
                continue
            in_range = []
            for r in sess.get("requests") or []:
                if isinstance(r, dict):
                    ts = parse_ts(r.get("timestamp"))
                    if ts and since <= ts < until:
                        in_range.append((ts, r))
            if not in_range:
                continue
            credits, missing, per_model = 0.0, 0, defaultdict(float)
            for _, r in in_range:
                c = r.get("copilotCredits")
                if is_num(c):
                    credits += c
                    per_model[model_of(r)] += c
                else:
                    missing += 1
            files = [f]
            if ws:
                t = ws / "GitHub.copilot-chat" / "transcripts" / f"{f.stem}.jsonl"
                if t.exists():
                    files.append(t)
            notes = []
            if missing:
                notes.append(f"{missing} requests without credits")
            outside = len(sess.get("requests") or []) - len(in_range)
            if outside > 0:
                notes.append(f"file also contains {outside} requests outside range")
            chats.append(dict(
                source="VS Code", id=f.stem, files=files,
                workspace=(workspace_path(ws) or ws.name) if ws else "<no folder>",
                title=title_of(sess, [r for _, r in in_range]),
                first=min(t for t, _ in in_range), last=max(t for t, _ in in_range),
                requests=len(in_range), credits=credits,
                models=dict(per_model), note="; ".join(notes)))
    return chats


# ===================================================================== CLI / app
def read_yaml_field(path, field):
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(rf"^\s*{re.escape(field)}\s*:\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip("'\"")
    except OSError:
        pass
    return ""


def cli_files(session_dir, full):
    if not full:
        return [session_dir / n for n in ("events.jsonl", "workspace.yaml")
                if (session_dir / n).exists()]
    out = [p for p in sorted(session_dir.rglob("*"))
           if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES]
    # events.jsonl first
    out.sort(key=lambda p: (p.name != "events.jsonl", str(p)))
    return out


def collect_cli(home, since, until, full):
    chats = []
    state = home / "session-state"
    if not state.is_dir():
        return chats
    for d in state.iterdir():
        ev = d / "events.jsonl" if d.is_dir() else (d if d.suffix == ".jsonl" else None)
        if ev is None or not ev.exists() or mtime_utc(ev) < since:
            continue
        first = last = snap_ts = None
        events_in_range = user_msgs = 0
        snap, models, title = None, {}, ""
        for e in iter_jsonl(ev):
            if not isinstance(e, dict):
                continue
            ts = parse_ts(e.get("timestamp"))
            if ts is None:
                continue
            etype = str(e.get("type", ""))
            if since <= ts < until:
                events_in_range += 1
                first = first or ts
                last = ts
                if etype == "user.message":
                    user_msgs += 1
                    if not title:
                        content = (e.get("data") or {}).get("content")
                        if isinstance(content, str):
                            title = " ".join(content.split())[:80]
            if etype == "session.shutdown":
                data = e.get("data") or {}
                s = data.get("accountingSnapshot") or {}
                if is_num(s.get("totalNanoAiu")):
                    snap, snap_ts, models = s, ts, data.get("modelMetrics") or {}
        if not events_in_range:
            continue
        counted = snap is not None and since <= snap_ts < until
        if snap is None:
            note = "no shutdown snapshot (credits unknown)"
        elif not counted:
            note = f"session ended {local_str(snap_ts)}, outside range: credits not counted here"
        else:
            note = "" if snap.get("aiCreditsStatus", "complete") == "complete" \
                else f"aiCreditsStatus={snap.get('aiCreditsStatus')}"
        is_dir = ev.name == "events.jsonl"
        ws_yaml = ev.parent / "workspace.yaml" if is_dir else None
        cwd = read_yaml_field(ws_yaml, "cwd") if ws_yaml and ws_yaml.exists() else ""
        chats.append(dict(
            source="CLI/app", id=ev.parent.name if is_dir else ev.stem,
            files=cli_files(ev.parent, full) if is_dir else [ev],
            workspace=cwd, title=title, first=first, last=last, requests=user_msgs,
            credits=float(snap["totalNanoAiu"]) / NANO_PER_CREDIT if counted else 0.0,
            models={m: None for m in models}, note=note))
    return chats


# ==================================================================== markdown
def fence_for(text):
    """A backtick fence longer than any backtick run inside the text."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def lang_for(path):
    return {".jsonl": "jsonl", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".md": "markdown", ".py": "python", ".ps1":
            "powershell"}.get(path.suffix.lower(), "text")


def write_markdown(out, chats, start, end, vs, cli):
    vs_total = sum(c["credits"] for c in vs)
    cli_total = sum(c["credits"] for c in cli)
    total = vs_total + cli_total
    per_model = defaultdict(float)
    for c in vs:
        for m, v in c["models"].items():
            per_model[m] += v

    with open(out, "w", encoding="utf-8", newline="\n") as w:
        w.write(f"# GitHub Copilot chats {start} .. {end}\n\n")
        w.write(f"Generated {datetime.now():%Y-%m-%d %H:%M}. Range in local time, both "
                "ends inclusive.\n\n")

        # ---------- summary
        w.write("## Summary\n\n")
        w.write("| Source | Chats | Requests in range | Credits |\n|---|---:|---:|---:|\n")
        w.write(f"| VS Code | {len(vs)} | {sum(c['requests'] for c in vs)} | "
                f"{vs_total:,.2f} |\n")
        w.write(f"| CLI / app | {len(cli)} | {sum(c['requests'] for c in cli)} | "
                f"{cli_total:,.2f} |\n")
        w.write(f"| **Total** | **{len(vs) + len(cli)}** | | **{total:,.2f}** "
                f"(~${total / 100:,.2f}) |\n\n")
        if per_model:
            w.write("**VS Code credits by model**\n\n| Model | Credits |\n|---|---:|\n")
            for m, v in sorted(per_model.items(), key=lambda kv: -kv[1]):
                w.write(f"| {md_cell(m)} | {v:,.2f} |\n")
            w.write("\n")
        w.write("CLI/app credits are session totals (`totalNanoAiu` / 1e9), counted in the "
                "range where "
                "the session ended.\n\n")

        # ---------- index
        w.write("## Index\n\n")
        w.write("| # | Source | First activity | Last activity | Workspace / cwd | Title | "
                "Requests | Credits | Models | Note |\n")
        w.write("|---:|---|---|---|---|---|---:|---:|---|---|\n")
        for i, c in enumerate(chats, 1):
            head = f"{i}. {c['source']} {c['id']}"
            w.write(f"| [{i}](#{anchor(head)}) | {c['source']} | {local_str(c['first'])} | "
                    f"{local_str(c['last'])} "
                    f"| {md_cell(c['workspace'])} | {md_cell(c['title'])} | "
                    f"{c['requests']} | {c['credits']:,.2f} "
                    f"| {md_cell(', '.join(c['models']))} | {md_cell(c['note'])} |\n")
        w.write("\n---\n\n")

        # ---------- full content
        for i, c in enumerate(chats, 1):
            w.write(f"## {i}. {c['source']} {c['id']}\n\n")
            w.write(f"- **Workspace / cwd:** {c['workspace'] or '-'}\n")
            if c["title"]:
                w.write(f"- **Title:** {c['title']}\n")
            w.write(f"- **Activity in range:** {local_str(c['first'])} .. "
                    f"{local_str(c['last'])}\n")
            w.write(f"- **Requests in range:** {c['requests']}  |  **Credits:** "
                    f"{c['credits']:,.4f}\n")
            if c["models"]:
                w.write(f"- **Models:** {', '.join(c['models'])}\n")
            if c["note"]:
                w.write(f"- **Note:** {c['note']}\n")
            w.write("\n")
            for f in c["files"]:
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    text = f"<could not read file: {e}>"
                fence = fence_for(text)
                w.write(f"### `{f}`\n\n")
                nl = "" if text.endswith("\n") else "\n"
                w.write(f"{fence}{lang_for(f)}\n{text}{nl}{fence}\n\n")
            w.write("---\n\n")
    return vs_total, cli_total


# ======================================================================== main
def main():
    ap = argparse.ArgumentParser(description="Collect GitHub Copilot chats of a date range "
                                             "into one Markdown file.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--current", action="store_true",
                   help="1st of the current month .. today  (YYYY-MM.md)")
    g.add_argument("--last", action="store_true", help="whole previous month  (YYYY-MM.md)")
    g.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                   help="start date, inclusive (FROM_TO.md)")
    ap.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                    help="end date, inclusive (default: today)")
    ap.add_argument("--out", default=".",
                    help="folder where the .md file is written (default: current folder)")
    ap.add_argument("--overwrite", action="store_true", help="replace the .md file if it exists")
    ap.add_argument("--full", action="store_true",
                    help="include every text file of the CLI session folders")
    ap.add_argument("--copilot-home", default=os.environ.get("COPILOT_HOME",
                                                              str(Path.home() / ".copilot")))
    ap.add_argument("--vscode-user", action="append", help="VS Code 'User' folder (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="list the chats, write nothing")
    args = ap.parse_args()
    if args.date_to and not args.date_from:
        ap.error("--to requires --from")

    start, end, name = resolve_range(args)
    since, until = to_utc_bounds(start, end)
    out = Path(args.out).expanduser().resolve() / f"{name}.md"

    vs = collect_vscode(vscode_user_dirs(args.vscode_user), since, until)
    cli = collect_cli(Path(args.copilot_home).expanduser(), since, until, args.full)
    chats = sorted(vs + cli, key=lambda c: c["first"])

    print(f"Range  : {start} .. {end}  (local time, inclusive)")
    print(f"Output : {out}")
    print(f"Found  : {len(vs)} VS Code chats, {len(cli)} CLI/app sessions")

    if args.dry_run:
        for c in chats:
            print(f"  {local_str(c['first'])}  {c['source']:<8} "
                  f"{c['credits']:>9.2f}  {c['workspace']}  [{c['id']}]")
        t1, t2 = sum(c["credits"] for c in vs), sum(c["credits"] for c in cli)
        print(f"Credits: VS Code {t1:.2f} + CLI/app {t2:.2f} = {t1 + t2:.2f}")
        return

    if out.exists() and not args.overwrite:
        sys.exit(f"{out} already exists. Use --overwrite to replace it.")
    out.parent.mkdir(parents=True, exist_ok=True)

    vs_total, cli_total = write_markdown(out, chats, start, end, vs, cli)
    size_mb = out.stat().st_size / 1e6
    print(f"Credits: VS Code {vs_total:.2f} + CLI/app {cli_total:.2f} = "
          f"{vs_total + cli_total:.2f}")
    print(f"Written: {out}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
