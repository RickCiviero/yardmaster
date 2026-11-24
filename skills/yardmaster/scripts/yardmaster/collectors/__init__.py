"""History collectors, one per harness. Each is read-only and returns normalised Chat records."""

import math
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from yardmaster.model import Chat
from yardmaster.safe_io import has_link_below


@dataclass
class CollectorContext:
    since: datetime  # inclusive, UTC
    until: datetime  # exclusive, UTC
    env: Mapping[str, str]
    platform: str
    roots: list[Path] | None = None  # explicit history roots (override discovery)
    project: Path | None = None  # keep only chats whose workspace is this project
    warnings: list[str] = field(default_factory=list)  # skipped files etc.; never contains chat text


COLLECTORS: dict[str, Callable[[CollectorContext], list[Chat]]] = {}


def mtime_utc(p: Path) -> datetime:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
    except OSError:
        return datetime.min.replace(tzinfo=UTC)


def skip_linked(ctx: CollectorContext, path: Path, root: Path) -> bool:
    """Never follow a link planted inside a history folder: it could point the collector at files that are not chats."""
    if not has_link_below(path, root):
        return False
    note = "skipped file(s) reached through a symlink or junction inside the history folder"
    if note not in ctx.warnings:
        ctx.warnings.append(note)
    return True


def nat(v: object) -> int:
    """A token count from untrusted JSON: a finite number in 0..1e9, else 0."""
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 10**9
    return int(v) if ok else 0


def in_project(workspace: str, project: Path) -> bool:
    norm = lambda s: os.path.normcase(os.path.normpath(str(s)))  # noqa: E731
    w, p = norm(workspace), norm(project)
    return w == p or w.startswith(p + os.sep)


from . import claude_code, codex, copilot_cli, vscode_copilot  # noqa: E402,F401  (each registers itself in COLLECTORS)
