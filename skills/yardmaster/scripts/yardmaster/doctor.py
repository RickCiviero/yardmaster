"""Read-only health check: what Yardmaster can see, what it can write, and what is still unverified."""

import os
import sys
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path

from .catalog import default_catalog
from .collectors import CollectorContext
from .collectors.claude_code import _root as claude_root
from .collectors.codex import _root as codex_root
from .collectors.copilot_cli import _home as copilot_home
from .paths import vscode_user_dirs
from .settings import load_settings

Row = tuple[str, str, str]  # (check, ok|warn|fail, detail)
FORMATS = {
    "vscode-copilot": ("ok", "router format taken from a real file (VS Code 1.147)"),
    "copilot-cli": ("warn", "custom-agent format not verified against a live Copilot CLI"),
    "claude-code": ("warn", "subagent / CLAUDE.md format not verified against a live Claude Code"),
    "codex": ("warn", "profile / AGENTS.md format not verified against a live Codex"),
}


def _writable(p: Path) -> tuple[str, str]:
    probe = p
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not os.access(probe, os.W_OK):
        return "warn", f"{p} is not writable"
    return "ok", f"{p}" + ("" if p.exists() else " (will be created)")


def doctor(
    env: Mapping[str, str], platform: str, *, today: date | None = None, policy: Path | None = None, config: Path | None = None
) -> list[Row]:
    today = today or date.today()
    rows: list[Row] = []
    v = sys.version_info
    rows.append(("python", "ok" if tuple(v[:3]) >= (3, 11, 0) else "fail",
                 f"{v[0]}.{v[1]}.{v[2]}" + ("" if tuple(v[:3]) >= (3, 11, 0) else " (3.11 or newer is required)")))

    ctx = CollectorContext(datetime.now(UTC), datetime.now(UTC), env, platform)
    vs = vscode_user_dirs(env, platform)
    n_vs = sum(len(list(u.glob("workspaceStorage/*/chatSessions/*.json*"))) + len(list(u.glob("globalStorage/emptyWindowChatSessions/*.json*")))
               for u in vs)
    cli = copilot_home(ctx) / "session-state"
    cc = claude_root(ctx) / "projects"
    cx = codex_root(ctx) / "sessions"
    found = {
        "vscode-copilot": (bool(vs), f"{n_vs} chat file(s) in {len(vs)} VS Code dir(s)"),
        "copilot-cli": (cli.is_dir(), f"{len(list(cli.iterdir())) if cli.is_dir() else 0} session(s) in {cli}"),
        "claude-code": (cc.is_dir(), f"{len(list(cc.glob('*/*.jsonl'))) if cc.is_dir() else 0} session files in {cc}"),
        "codex": (cx.is_dir(), f"{len(list(cx.rglob('rollout-*.jsonl'))) if cx.is_dir() else 0} session files in {cx}"),
    }
    for h, (ok, detail) in found.items():
        rows.append((f"history:{h}", "ok" if ok else "warn", detail if ok else "not found (this tool is not used here, or stores history elsewhere)"))

    rows.append(("write:project", *_writable(Path.cwd())))
    cfg = {"claude-code": Path(env["CLAUDE_CONFIG_DIR"]) if env.get("CLAUDE_CONFIG_DIR") else claude_root(ctx),
           "codex": codex_root(ctx), "copilot-cli": copilot_home(ctx)}
    for h, p in cfg.items():
        rows.append((f"write:{h}", *_writable(p)))
    for h, (status, detail) in FORMATS.items():
        rows.append((f"format:{h}", status, detail))

    try:
        s = load_settings(env, platform, policy=policy, config=config)
        src = s.sources
        rows.append(("settings", "ok",
                     f"deny_models={sorted(s.deny_models) or 'none'} ({src['deny_models']}); "
                     f"harnesses={sorted(s.harnesses) if s.harnesses is not None else 'all'} ({src['harnesses']}); "
                     f"redact_pii={s.redact_pii} ({src['redact_pii']}); max_batches={s.max_batches} ({src['max_batches']})"))
    except ValueError as e:
        rows.append(("settings", "fail", str(e)))
    try:
        cat = default_catalog()
        n = sum(len(cat.models(h)) for h in cat.harnesses())
        days = (today - date.fromisoformat(cat.as_of)).days
        rows.append(("catalog", "warn", f"{n} models in {len(cat.harnesses())} harnesses, as of {cat.as_of} ({days} days old); "
                                        "tiers are assumptions and the GPT-6 names are not yet confirmed in a live install"))
    except ValueError as e:
        rows.append(("catalog", "fail", str(e)))
    return rows


def render_doctor(rows: list[Row]) -> str:
    return "\n".join(f"[{status:<4}] {name:<24} {detail}" for name, status, detail in rows) + "\n"
