"""GitHub Copilot CLI: custom agents with a `model:` field, plus a routing block in AGENTS.md.

shortcut: that Copilot CLI honours `model:` in agent profiles is ASSUMED, not verified (open owner task); if it does
not, the AGENTS.md guidance still tells the agent which profile to pick.
"""

from collections.abc import Mapping
from pathlib import Path

from yardmaster.blocks import replace_block
from yardmaster.resolve import ResolvedGroup
from yardmaster.schema import Plan

from . import WRITERS, FileChange, block_note, examples_text, frontmatter, home, lead, read_old, sentence


def _agent(g: ResolvedGroup) -> str:
    body = f"Handle {lead(g.when)}.{examples_text(g)}\n"
    return frontmatter(name=f"ym-{g.name}", description=g.when, model=g.model.id) + body


def write(plan: Plan, groups: list[ResolvedGroup], root: Path, global_: bool, env: Mapping[str, str]) -> list[FileChange]:
    base = Path(env["COPILOT_HOME"]) if env.get("COPILOT_HOME") else home(env) / ".copilot"
    agents_dir, cfg_root = (base / "agents", base) if global_ else (root / ".github" / "agents", root)
    changes = [FileChange(p := agents_dir / f"ym-{g.name}.agent.md", cfg_root, read_old(p), _agent(g)) for g in groups]
    if not global_:  # shortcut: no documented user-level instructions file for the CLI, so global writes agents only
        items = "\n".join(f"- `ym-{g.name}` ({g.model.id}): {sentence(g.when)}." for g in groups)
        body = (f"## Model routing (Yardmaster)\n\n{block_note()}\n\n"
                f"Pick the matching custom agent for each kind of work:\n\n{items}")
        p = root / "AGENTS.md"
        old = read_old(p)
        changes.append(FileChange(p, root, old, replace_block(old or "", body, style="md")))
    return changes


WRITERS["copilot-cli"] = write
