"""History collectors, one per harness. Each is read-only and returns normalised Chat records."""

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from yardmaster.model import Chat


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


def in_project(workspace: str, project: Path) -> bool:
    norm = lambda s: os.path.normcase(os.path.normpath(str(s)))  # noqa: E731
    w, p = norm(workspace), norm(project)
    return w == p or w.startswith(p + os.sep)


from . import claude_code, copilot_cli, vscode_copilot  # noqa: E402,F401  (each registers itself in COLLECTORS)
