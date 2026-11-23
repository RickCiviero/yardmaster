# 🚦 Yardmaster

**Right job. Right track. Lowest fare.**

> *Thirty years in the switchyard. I never once sent a locomotive to haul a postcard.*

## Meet the Yardmaster

The Yardmaster has run the same switchyard for thirty years: worn cap, pocket watch, a ledger in the breast pocket. He has seen every kind of freight come through. A heavy load goes to the big engine, a parcel goes on the handcar, and nobody pays for more track than the job needs. He doesn't trust a shipment without a manifest, and he never throws a switch without someone signing for it.

Yardmaster does the same for your AI coding agents. It reads your past chats in GitHub Copilot, Claude Code and Codex, works out which **kind of work** each one was and the **cheapest model that would still have done it right**, then writes the model-routing config for your harness, after you approve the diff.

## Status: planned, not built yet

This repository currently holds the **design**. Nothing is installable yet.

| Document | What it is |
|---|---|
| [`docs/superpowers/specs/2026-11-23-yardmaster-design.md`](docs/superpowers/specs/2026-11-23-yardmaster-design.md) | The approved design: goals, harness coverage, security model, brand |
| [`reference/copilot_chats_to_md.py`](reference/copilot_chats_to_md.py) | The original manual script Yardmaster replaces (behavioural reference) |

## How to build it with Claude Code

1. Clone this repo and open it in Claude Code:
   ```sh
   git clone https://github.com/RickCiviero/yardmaster
   cd yardmaster
   claude
   ```
2. Install the [superpowers](https://github.com/obra/superpowers) plugin if you don't have it:
   `/plugin marketplace add obra/superpowers-marketplace` → `/plugin install superpowers@superpowers-marketplace`
3. Tell Claude Code:
   > Read `docs/superpowers/specs/2026-11-23-yardmaster-design.md`, write an implementation plan for v1 with superpowers:writing-plans, then build it with superpowers:subagent-driven-development. Stop at every step that needs real history from my machine and ask me.
4. Steps marked **verify** need real history from your machines (Copilot in VS Code, Copilot CLI, Claude Code, Codex). `tools/make_fixture.py` anonymises those files before they become test fixtures. Real chat text never enters the repo.

## What v1 will do

- `/yardmaster`: survey → redact → analyse with the model you're already using → propose routes → show diff → you approve → write.
- `/yardmaster ledger`: what you spent, per harness and model. No AI call.
- `/yardmaster undo`: put the previous config back.
- Writes `.agents/model-router/yardmaster.model-router.yml` (VS Code Copilot), Copilot CLI agents, Claude Code subagents plus a `CLAUDE.md` block, and Codex profiles plus an `AGENTS.md` block.
- Windows, macOS and Linux. Python 3.11+, standard library only.

## Security, in one breath

Runs locally with no network of its own. Secrets are redacted before anything is sent. Chat text is treated as untrusted data. Model output must pass strict schemas. It writes only to allow-listed files, inside marked blocks, after you approve a diff, with a backup and undo. Releases are signed with build provenance. A penetration-test suite runs in CI on all three OSes. Details are in §9 of the design.

## Licence

[MIT](LICENSE) © 2026 RickCiviero
