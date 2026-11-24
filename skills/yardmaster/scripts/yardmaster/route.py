"""Preview, approve, apply and undo routing changes.

`dry_run` renders every target, pins each file's current hash and stores the exact text it will write. `apply`
writes ONLY that stored text, only if every target still has the previewed hash, only to allow-listed file names
inside the recorded root, all-or-nothing (a failed write rolls back). `undo` restores the backups, but only if the
user has not edited the files since.
"""

import difflib
import json
import os
import re
import secrets
import shutil
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import writers
from .paths import state_dir
from .pricing import Pricing, default_pricing
from .resolve import resolve_plan
from .safe_io import MAX_JSON, UnsafePathError, atomic_write, check_target, load_json, sha256_file, write_bytes_atomic
from .schema import validate_plan
from .settings import Settings, load_settings
from .writers import WRITERS, FileChange

RUN_ID = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I/O: easy to read out and type
MAX_TEXT = 1_000_000
# A record is only a request to write these names: even a tampered record cannot write anything else.
ALLOWED = [re.compile(p) for p in (
    r"\.agents/model-router/[A-Za-z0-9._-]+\.model-router\.yml",
    r"\.github/agents/ym-[a-z0-9-]+\.agent\.md",
    r"\.claude/agents/ym-[a-z0-9-]+\.md",
    r"agents/ym-[a-z0-9-]+(\.agent)?\.md",
    r"AGENTS\.md",
    r"CLAUDE\.md",
    r"config\.toml",  # v1.0.0 wrote Codex profiles here; kept so `undo` can restore those runs
    r"ym-[a-z0-9-]+\.config\.toml",
)]


class RouteError(Exception):
    pass


@dataclass
class RunRecord:
    run_id: str
    created: str
    code: str
    changes: list[dict]  # {path, root, sha256_before, existed, new_text[, written_sha256]}
    applied: bool = False
    undone: bool = False
    targets: list[str] = field(default_factory=list)
    project_root: str = ""


# ------------------------------------------------------------------------------------------ storage
def _run_dir(run_id: str, env, platform) -> Path:
    if not isinstance(run_id, str) or not RUN_ID.match(run_id):
        raise RouteError("bad run id (expected like 20261123T101500Z-ab12cd)")
    return state_dir(env, platform) / "runs" / run_id


def _save(rec: RunRecord, env, platform) -> None:
    d = _run_dir(rec.run_id, env, platform)
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(d / "record.json", os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(json.dumps(asdict(rec), indent=1).encode("utf-8"))


def _load(run_id: str, env, platform) -> RunRecord:
    f = _run_dir(run_id, env, platform) / "record.json"
    doc = load_json(f) if f.is_file() else None
    if doc is None:
        raise RouteError(f"no such run {run_id}")
    try:
        rec = RunRecord(**doc)
        assert isinstance(rec.changes, list) and isinstance(rec.code, str) and rec.run_id == run_id
        for ch in rec.changes:
            _check_change(ch)
    except (TypeError, AssertionError, KeyError) as e:
        raise RouteError("the run record is damaged") from e
    return rec


def _check_change(ch: dict) -> tuple[Path, Path]:
    if not (isinstance(ch, dict) and all(isinstance(ch.get(k), str) for k in ("path", "root", "new_text"))):
        raise RouteError("the run record is damaged")
    if len(ch["new_text"]) > MAX_TEXT or ch.get("sha256_before") is not None and not isinstance(ch["sha256_before"], str):
        raise RouteError("the run record is damaged")
    path, root = Path(ch["path"]), Path(ch["root"])
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        raise RouteError(f"{path} is outside {root}") from None
    if not any(p.fullmatch(rel) for p in ALLOWED):
        raise RouteError(f"{rel} is not a file Yardmaster writes")
    return path, root


# ------------------------------------------------------------------------------------------ dry run
def render_diff(changes: list[FileChange]) -> str:
    out = []
    for c in changes:
        rel = c.path.relative_to(c.root).as_posix()
        old = (c.old or "").replace("\r\n", "\n").splitlines(keepends=True)
        new = c.new.replace("\r\n", "\n").splitlines(keepends=True)
        out.append(f"=== {c.path}" + (" (new file)" if c.old is None else ""))
        diff = difflib.unified_diff(old, new, "/dev/null" if c.old is None else f"a/{rel}", f"b/{rel}")
        out.append("".join(line if line.endswith("\n") else line + "\n" for line in diff))
    return "\n".join(out)


def dry_run(
    plan_path: Path, targets: list[str], project_root: Path, global_: bool, env: Mapping[str, str], platform: str,
    *, settings: Settings | None = None, pricing: Pricing | None = None,
) -> RunRecord:
    settings = settings or load_settings(env, platform)
    pricing = pricing or default_pricing(env, platform)
    doc = load_json(Path(plan_path), MAX_JSON)
    if doc is None:
        raise RouteError(f"cannot read {plan_path} as JSON")
    plan = validate_plan(doc, pricing=pricing)  # raises ValidationError before anything else happens
    if not targets:
        raise RouteError("no target given")
    for t in targets:
        if t not in WRITERS:
            raise RouteError(f"unknown target {t!r}; known: {', '.join(WRITERS)}")
        if settings.harnesses is not None and t not in settings.harnesses:
            raise RouteError(f"target {t!r} is not allowed by policy")

    root = Path(project_root)
    rendered: list[FileChange] = []
    try:
        for t in targets:  # later targets see earlier ones' output, so a shared AGENTS.md keeps every block
            groups = resolve_plan(plan, t, pricing, settings.deny_models)
            for c in WRITERS[t](plan, groups, root, global_, env):
                writers.overlay_set(c.path, c.new)
                rendered.append(c)
    finally:
        writers.overlay_clear()
    merged: dict[Path, FileChange] = {}
    for c in rendered:
        merged[c.path] = FileChange(c.path, c.root, merged[c.path].old if c.path in merged else c.old, c.new)
    changes = [c for c in merged.values() if (c.old or "").replace("\r\n", "\n") != c.new.replace("\r\n", "\n") or c.old is None]

    records = []
    for c in changes:
        sha = sha256_file(c.path)
        try:
            check_target(c.path, c.root, sha)
        except UnsafePathError as e:
            raise RouteError(str(e)) from None
        records.append({"path": str(c.path), "root": str(c.root), "sha256_before": sha, "existed": c.path.exists(),
                        "new_text": c.new})
    rec = RunRecord(
        run_id=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3),
        created=datetime.now(UTC).isoformat(timespec="seconds"),
        code="".join(secrets.choice(CODE_ALPHABET) for _ in range(4)),
        changes=records, targets=list(targets), project_root=str(root),
    )
    _save(rec, env, platform)
    report = [f"# Yardmaster run {rec.run_id}", "", f"Targets: {', '.join(targets)}", f"Project: {root}",
              f"Global: {'yes' if global_ else 'no'}", "", "Files:"]
    report += [f"- {c.path} ({'new' if c.old is None else 'modified'})" for c in changes] or ["- (none: already up to date)"]
    (_run_dir(rec.run_id, env, platform) / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    if changes:
        print(render_diff(changes))
    else:
        print("Everything is already up to date: no files would change.")
    print(f"Run id: {rec.run_id}")
    print(f"Approval code: {rec.code}")
    print(f"Apply with: yardmaster route --apply {rec.run_id} --code {rec.code}")
    return rec


# ------------------------------------------------------------------------------------------ apply
def _prune_empty(path: Path, root: Path) -> None:
    for parent in path.parents:
        if parent == root or root not in parent.parents:
            break
        try:
            parent.rmdir()
        except OSError:
            break


def _restore(changes: list[dict], backups: Path, upto: int) -> list[str]:
    errors = []
    for i, ch in enumerate(changes[:upto]):
        path, root = Path(ch["path"]), Path(ch["root"])
        try:
            if ch["existed"]:
                write_bytes_atomic(path, (backups / f"{i}.bak").read_bytes())
            else:
                path.unlink(missing_ok=True)
                _prune_empty(path, root)
        except OSError as e:
            errors.append(f"{path}: {e}")
    return errors


def apply(run_id: str, code: str | None, *, interactive: bool, env: Mapping[str, str], platform: str) -> list[Path]:
    rec = _load(run_id, env, platform)
    if rec.applied:
        raise RouteError("this run was already applied")
    if code is None and interactive:
        code = input(f"Type the approval code shown with the diff ({len(rec.code)} letters): ")
    if code is not None and code.strip().upper() != rec.code:
        raise RouteError("wrong approval code")

    targets = [_check_change(ch) for ch in rec.changes]
    for ch, (path, root) in zip(rec.changes, targets, strict=True):  # preflight EVERYTHING before touching anything
        try:
            check_target(path, root, ch.get("sha256_before"))
        except UnsafePathError as e:
            raise RouteError(str(e)) from None

    backups = _run_dir(run_id, env, platform) / "backup"
    backups.mkdir(parents=True, exist_ok=True)
    for i, (ch, (path, _)) in enumerate(zip(rec.changes, targets, strict=True)):
        if ch["existed"]:
            (backups / f"{i}.bak").write_bytes(path.read_bytes())
    done = 0
    try:
        for ch, (path, root) in zip(rec.changes, targets, strict=True):
            atomic_write(path, ch["new_text"], root=root, expect_sha256=ch.get("sha256_before"))
            done += 1
    except BaseException:
        _restore(rec.changes, backups, done)
        raise
    for ch, (path, _) in zip(rec.changes, targets, strict=True):
        ch["written_sha256"] = sha256_file(path)
    rec.applied = True
    _save(rec, env, platform)
    return [p for p, _ in targets]


# ------------------------------------------------------------------------------------------ undo
def undo(run_id: str | None, env: Mapping[str, str], platform: str) -> list[Path]:
    if run_id is None:
        runs = state_dir(env, platform) / "runs"
        rec = None
        for d in sorted(runs.iterdir(), reverse=True) if runs.is_dir() else []:
            try:
                cand = _load(d.name, env, platform)
            except RouteError:
                continue
            if cand.applied and not cand.undone:
                rec = cand
                break
        if rec is None:
            raise RouteError("nothing to undo")
    else:
        rec = _load(run_id, env, platform)
        if rec.undone:
            raise RouteError("this run was already undone")
        if not rec.applied:
            raise RouteError("this run was never applied")
    targets = [_check_change(ch) for ch in rec.changes]
    edited = [str(p) for ch, (p, _) in zip(rec.changes, targets, strict=True) if sha256_file(p) != ch.get("written_sha256")]
    if edited:
        raise RouteError("refusing to undo: these files were edited since the run: " + ", ".join(edited))
    backups = _run_dir(rec.run_id, env, platform) / "backup"
    errors = _restore(rec.changes, backups, len(rec.changes))
    if errors:
        raise RouteError("undo was incomplete: " + "; ".join(errors))
    rec.undone = True
    _save(rec, env, platform)
    shutil.rmtree(backups, ignore_errors=True)
    return [p for p, _ in targets]
