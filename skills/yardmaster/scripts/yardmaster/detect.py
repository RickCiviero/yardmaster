from collections.abc import Mapping


def detect_harness(env: Mapping[str, str]) -> str | None:
    """Which harness is running this process, judged from its environment (best effort)."""
    if env.get("CLAUDECODE") or env.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude-code"
    if any(k.startswith("CODEX_") and k != "CODEX_HOME" for k in env):
        return "codex"
    if any(k.startswith("COPILOT_") and k != "COPILOT_HOME" for k in env):
        return "copilot-cli"
    if env.get("TERM_PROGRAM") == "vscode":
        return "vscode-copilot"
    return None
