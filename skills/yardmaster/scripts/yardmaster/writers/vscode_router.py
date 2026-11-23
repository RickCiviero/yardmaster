"""VS Code Copilot (1.147+): <project>/.agents/model-router/yardmaster.model-router.yml, the owner's router format."""

from collections.abc import Mapping
from pathlib import Path

from yardmaster.emit import yaml_str
from yardmaster.resolve import ResolvedGroup
from yardmaster.schema import Plan

from . import WRITERS, FileChange, header, read_old


def write(plan: Plan, groups: list[ResolvedGroup], root: Path, global_: bool, env: Mapping[str, str]) -> list[FileChange]:
    if global_:
        raise ValueError("vscode-copilot has no global router; the router file lives in the project")
    path = root / ".agents" / "model-router" / "yardmaster.model-router.yml"
    lines = [header("#"), "version: 1", f"description: {yaml_str(plan.description)}", "routes:"]
    for g in groups:  # most to least expensive
        lines += [f"  - model: {yaml_str(g.model.id)}", f"    when: {yaml_str(g.when)}"]
    return [FileChange(path, root, read_old(path), "\n".join(lines) + "\n")]


WRITERS["vscode-copilot"] = write
