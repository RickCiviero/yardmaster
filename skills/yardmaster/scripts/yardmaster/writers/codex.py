"""Codex CLI: one profile file per group, `<CODEX_HOME>/ym-<group>.config.toml`. Codex 0.134 and later read profiles from
these files only, not from `[profiles.*]` tables, so each profile is a whole file holding one top-level `model`. An
AGENTS.md block tells the agent which `codex --profile` to start with. Codex cannot switch models mid-session."""

import tomllib
from collections.abc import Mapping
from pathlib import Path

from yardmaster.blocks import BlockError, replace_block
from yardmaster.emit import toml_str
from yardmaster.resolve import ResolvedGroup
from yardmaster.schema import Plan

from . import WRITERS, FileChange, block_note, home, read_old, sentence


def _profile(group: ResolvedGroup, path: Path, old: str | None) -> str:
    if old is not None and "# yardmaster:begin" not in old:  # a profile we did not write is the user's: never overwrite it
        raise BlockError(f"{path.name} already exists and is not a Yardmaster profile; rename or remove it first")
    new = replace_block(old or "", f"# {block_note()}\nmodel = {toml_str(group.model.id)}", style="hash")
    try:
        tomllib.loads(new)
    except tomllib.TOMLDecodeError as e:  # never write a profile Codex cannot read
        raise BlockError("the result would not be valid TOML") from e
    return new


def write(plan: Plan, groups: list[ResolvedGroup], root: Path, global_: bool, env: Mapping[str, str]) -> list[FileChange]:
    cx = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else home(env) / ".codex"
    changes = []
    for g in groups:
        p = cx / f"ym-{g.name}.config.toml"
        old = read_old(p)
        changes.append(FileChange(p, cx, old, _profile(g, p, old)))
    items = "\n".join(f"- `codex --profile ym-{g.name}` ({g.model.id}): {sentence(g.when)}." for g in groups)
    body = (f"## Model routing (Yardmaster)\n\n{block_note()}\n\nCodex cannot change model mid-session. "
            f"Start it with the profile that matches the kind of work:\n\n{items}")
    agents_root = cx if global_ else root
    p = agents_root / "AGENTS.md"
    a_old = read_old(p)
    changes.append(FileChange(p, agents_root, a_old, replace_block(a_old or "", body, style="md", tag="codex")))
    return changes


WRITERS["codex"] = write
