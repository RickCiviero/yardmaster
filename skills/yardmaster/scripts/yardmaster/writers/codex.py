"""Codex CLI: one `[profiles.ym-<group>]` per group in ~/.codex/config.toml (profiles are user-level), plus an
AGENTS.md block telling the agent which `codex --profile` to start with. Codex cannot switch models mid-session."""

import tomllib
from collections.abc import Mapping
from pathlib import Path

from yardmaster.blocks import BlockError, replace_block
from yardmaster.emit import toml_str
from yardmaster.resolve import ResolvedGroup
from yardmaster.schema import Plan

from . import WRITERS, FileChange, block_note, home, read_old, sentence


def _profiles_block(groups: list[ResolvedGroup], old: str) -> str:
    try:  # our own profiles may exist ONLY inside our block: anything else is the user's and we do not touch it
        outside = tomllib.loads(replace_block(old, "", style="hash")).get("profiles", {})
    except tomllib.TOMLDecodeError as e:
        raise BlockError("the existing config.toml is not valid TOML; fix it first") from e
    if clash := sorted(k for k in outside if str(k).startswith("ym-")):
        raise BlockError(f"config.toml already defines profile(s) {', '.join(clash)} outside the Yardmaster block (names starting 'ym-')")
    body = "\n\n".join(f"[profiles.ym-{g.name}]\nmodel = {toml_str(g.model.id)}" for g in groups)
    new = replace_block(old, f"# {block_note()}\n{body}", style="hash")
    try:
        tomllib.loads(new)
    except tomllib.TOMLDecodeError as e:  # e.g. the user's file ends inside an open table: never emit a broken config
        raise BlockError("the result would not be valid TOML") from e
    return new


def write(plan: Plan, groups: list[ResolvedGroup], root: Path, global_: bool, env: Mapping[str, str]) -> list[FileChange]:
    cx = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else home(env) / ".codex"
    cfg = cx / "config.toml"
    old = read_old(cfg) or ""
    changes = [FileChange(cfg, cx, read_old(cfg), _profiles_block(groups, old))]
    items = "\n".join(f"- `codex --profile ym-{g.name}` ({g.model.id}): {sentence(g.when)}." for g in groups)
    body = (f"## Model routing (Yardmaster)\n\n{block_note()}\n\nCodex cannot change model mid-session. "
            f"Start it with the profile that matches the kind of work:\n\n{items}")
    agents_root = cx if global_ else root
    p = agents_root / "AGENTS.md"
    a_old = read_old(p)
    changes.append(FileChange(p, agents_root, a_old, replace_block(a_old or "", body, style="md")))
    return changes


WRITERS["codex"] = write
