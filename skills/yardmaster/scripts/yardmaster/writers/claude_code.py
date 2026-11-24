"""Claude Code: one subagent per task group (`model:` per file) + a delegation block in CLAUDE.md.

The group whose model is the MAIN session's model gets no subagent: that work simply stays in the session.
The session model comes from ANTHROPIC_MODEL when set, else the most expensive group is assumed.
"""

from collections.abc import Mapping
from pathlib import Path

from yardmaster.blocks import replace_block
from yardmaster.resolve import ResolvedGroup
from yardmaster.schema import Plan

from . import WRITERS, FileChange, block_note, examples_text, frontmatter, home, lead, read_old, sentence


def _main_group(groups: list[ResolvedGroup], env: Mapping[str, str]) -> ResolvedGroup:
    want = (env.get("ANTHROPIC_MODEL") or "").strip().lower()
    for g in groups:
        if want and want in {g.model.id.lower(), *(a.lower() for a in g.model.aliases)}:
            return g
    return groups[0]  # shortcut: no env hint -> assume the session runs the most expensive routed model


def write(plan: Plan, groups: list[ResolvedGroup], root: Path, global_: bool, env: Mapping[str, str]) -> list[FileChange]:
    cfg = Path(env["CLAUDE_CONFIG_DIR"]) if env.get("CLAUDE_CONFIG_DIR") else home(env) / ".claude"
    base = cfg if global_ else root
    agents_dir = cfg / "agents" if global_ else root / ".claude" / "agents"
    main = _main_group(groups, env)
    delegated = [g for g in groups if g is not main]
    changes = [
        FileChange(
            p := agents_dir / f"ym-{g.name}.md", base, read_old(p),
            frontmatter(name=f"ym-{g.name}", description=f"Use for: {g.when}", model=g.model.id)
            + f"Handle {lead(g.when)}.{examples_text(g)}\n",
        )
        for g in delegated
    ]
    items = "\n".join(f"- `ym-{g.name}` ({g.model.id}): {sentence(g.when)}." for g in delegated)
    body = (f"## Model routing (Yardmaster)\n\n{block_note()}\n\n"
            + (f"Delegate each kind of work to the matching subagent:\n\n{items}\n\n" if delegated else "")
            + f"Handle in the main session: {sentence(main.when)}.")
    p = base / "CLAUDE.md"
    old = read_old(p)
    changes.append(FileChange(p, base, old, replace_block(old or "", body, style="md")))
    return changes


WRITERS["claude-code"] = write
