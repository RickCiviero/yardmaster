# Supported harnesses

| Harness | History read from | Cost signal | Routing written to |
|---|---|---|---|
| GitHub Copilot in VS Code (and Insiders) | `<User>/workspaceStorage/*/chatSessions`, transcripts, empty-window sessions | Copilot credits per request | `.agents/model-router/yardmaster.model-router.yml` |
| GitHub Copilot CLI | `~/.copilot/session-state/*/events.jsonl` (`COPILOT_HOME`) | `totalNanoAiu` per session | `.github/agents/*.agent.md` and an `AGENTS.md` block |
| Claude Code | `~/.claude/projects/*/*.jsonl` (`CLAUDE_CONFIG_DIR`) | token usage times price | `.claude/agents/ym-*.md` and a `CLAUDE.md` block |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (`CODEX_HOME`) | token counts times price | profiles in `config.toml` and an `AGENTS.md` block |

Every collector honours its tool's home variable and accepts `--path HARNESS=DIR`.

## Verification status

The formats are built from each tool's documentation and anonymised fixtures. They are **not yet verified against live
installs** of VS Code Copilot, Copilot CLI, Claude Code and Codex. `/yardmaster doctor` repeats this for each one. Record
the tool versions and the outcome of each manual acceptance run here when it is done:

| Harness | Version tested | Accepted by owner |
|---|---|---|
| Copilot in VS Code | not yet | not yet |
| Copilot CLI | not yet | not yet |
| Claude Code | not yet | not yet |
| Codex | not yet | not yet |

## Roadmap

One harness per release, each with fixtures, pentest cases and documentation: v1.1 Cursor and cursor-agent, v1.2 Cline,
Roo and Kilo, v1.3 Gemini CLI and Qwen Code, v1.4 OpenCode, v1.5 Aider, v1.6 Continue, v1.7 Goose, v1.8 Windsurf, Zed,
JetBrains, Amp, Kiro, Augment, Warp and Trae, only where a stable readable local store exists.
