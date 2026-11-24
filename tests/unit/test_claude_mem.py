"""Claude-Mem's own observer sessions are not the user's work, so they are left out unless asked for."""

from types import SimpleNamespace

import pytest
from yardmaster.cli import _is_claude_mem


@pytest.mark.parametrize("workspace", [
    r"C:\Users\civie\.claude-mem\observer-sessions\-3",
    "/home/me/.claude-mem/observer-sessions/-2",
    r"C:\x\.claude-mem",
])
def test_claude_mem_sessions_are_recognised(workspace):
    assert _is_claude_mem(SimpleNamespace(workspace=workspace))


@pytest.mark.parametrize("workspace", [
    r"C:\Users\civie\Desktop\projects\yardmaster",
    "/home/me/claude-mem-notes",  # a folder whose name only contains the words
    "/home/me/.claude-memories",
    "",
    None,
])
def test_ordinary_workspaces_are_kept(workspace):
    assert not _is_claude_mem(SimpleNamespace(workspace=workspace))
