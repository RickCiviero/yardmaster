# Supported harnesses

| Harness | History read from | Cost signal | Routing written to |
|---|---|---|---|
| GitHub Copilot in VS Code (and Insiders) | `<User>/workspaceStorage/*/chatSessions`, transcripts, empty-window sessions | Copilot credits per request | `.agents/model-router/yardmaster.model-router.yml` |
| GitHub Copilot CLI | `~/.copilot/session-state/*/events.jsonl` (`COPILOT_HOME`) | `totalNanoAiu` per session | `.github/agents/*.agent.md` and an `AGENTS.md` block |
| Claude Code | `~/.claude/projects/*/*.jsonl` (`CLAUDE_CONFIG_DIR`) | token usage times price | `.claude/agents/ym-*.md` and a `CLAUDE.md` block |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (`CODEX_HOME`) | token counts times price | profile files `~/.codex/ym-<group>.config.toml` and an `AGENTS.md` block |

Every collector honours its tool's home variable and accepts `--path HARNESS=DIR`.

## Verification status

Checked on 2026-11-24. "Docs" means the tool's current official documentation. "CI" means the `install-check` run on fresh
Windows, macOS and Linux runners (run 45360499368).

| Harness | What was checked | Result |
|---|---|---|
| Claude Code | Subagent file format and `model` values against the subagent docs; `CLAUDE.md` locations against the memory docs | Matches the docs. `model` uses the documented aliases. The block markers are HTML comments that Claude Code strips; the instructions between them are kept |
| Claude Code plugin | `claude plugin marketplace add` and `install` on fresh runners (CI); `claude plugin validate .` locally | Installs and passes `doctor` on all three systems |
| Codex | Profile files against the Codex 0.134+ config docs | v1.0.0 was wrong: 0.134+ ignores the `[profiles.*]` tables it wrote. Fixed in 3a4d988, which writes profile files in `~/.codex` |
| Copilot CLI | Custom-agent location and front matter (`name`, `description`, `model`) against the docs | Location and keys match. The docs do not list allowed `model` values, so the model names written are unverified |
| VS Code Copilot | Router file: an owner-supplied format, checked against a real VS Code 1.147 file in the fixtures | Not checkable from the docs here |
| Release zip and `npx skills` | Install with `skills@1.9.0` (`-a codex`, `-a github-copilot`); zip checksum and `gh attestation verify` (CI) | Installs and passes `doctor` on all three systems |
| Gemini CLI | `gemini extensions install` with its consent flags (CI); `gemini extensions validate` locally | Installs and passes `doctor` on all three systems |

Still not verified: a real session in each harness. That needs the owner to run `/yardmaster` in each one, and then to
record the tool version and the outcome below.

### Local history acceptance (2026-11-24)

On this machine, `ledger` and `survey` ran over 17–24 November. Both were read-only: no chat was judged, and no config
file was written.

- Claude Code: 33 chats, 64 requests, $47.37 estimated spend, 15 batches.
- Redaction: 172 matches (generic secret 84, high-entropy 78, connection string 6, private-key block 2, URL credentials 2).
- Copilot CLI, VS Code Copilot and Codex: no chats in the range.
- Finding: 31 of the 33 chats are claude-mem observer sessions, not coding work. The default survey includes them. Until
  that changes, exclude them with `--exclude-workspace`. Whether to exclude them by default is an open decision.

### In-harness acceptance

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
