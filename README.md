<p align="center"><img src="assets/logo.svg" alt="Yardmaster logo: a railway semaphore over switch points" width="96"></p>

# Yardmaster

**Right job. Right track. Lowest fare.**

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/17065/badge)](https://www.bestpractices.dev/projects/17065)

> *Thirty years in the switchyard. I never once sent a locomotive to haul a postcard.*

## Meet the Yardmaster

The Yardmaster has run the same switchyard for thirty years: worn cap, pocket watch, a ledger in the breast pocket. He
has seen every kind of freight come through. A heavy load goes to the big engine, a parcel goes on the handcar, and
nobody pays for more track than the job needs. He doesn't trust a shipment without a manifest, and he never throws a
switch without someone signing for it.

Yardmaster does the same for your AI coding agents. It reads your past chats, works out which **kind of work** each one
was and the **weakest model that would still have done it right**, then writes the model-routing config for your
harness, after you approve the diff.

> **Status:** v1.1.1 is released. Manual acceptance on real history in each harness is still to do; see the [changelog](CHANGELOG.md).

## What it does

| | By hand | With Yardmaster |
|---|---|---|
| 1. See what it used | Export each harness's chats, add up credits and tokens | `/yardmaster ledger`: tokens and credits per harness, model and strength, no AI call |
| 2. Decide what needed which model | Read the chats yourself, or paste them into a model and trust the answer | `/yardmaster`: secrets are redacted, then the model you already use judges each chat |
| 3. Set up the routing | Hand-write YAML, TOML and Markdown for each tool | A diff you approve; one marked block per file; `/yardmaster undo` restores it |

## Install

Claude Code:

```
/plugin marketplace add RickCiviero/yardmaster
/plugin install yardmaster@yardmaster
```

Any agent that supports skills:

```
npx skills add RickCiviero/yardmaster
```

Codex or GitHub Copilot specifically:

```
npx skills add RickCiviero/yardmaster -a codex
npx skills add RickCiviero/yardmaster -a github-copilot
```

Gemini CLI: `gemini extensions install https://github.com/RickCiviero/yardmaster`. Or copy `skills/yardmaster/` into
your tool's skills folder by hand. You need Python 3.11 or newer; nothing else is installed.

Command only, without a harness: `pipx install https://github.com/RickCiviero/yardmaster/releases/download/v1.1.1/yardmaster-1.1.1-py3-none-any.whl`, then `yardmaster ledger`.

## Quick start

| Say | What happens |
|---|---|
| `/yardmaster` | Survey the last 30 days, judge each chat, show the plan and a diff, and write it only when you approve |
| `/yardmaster ledger` | What you spent, per harness and model. No analysis |
| `/yardmaster undo` | Put the previous config back |
| `/yardmaster doctor` | What can be read and written here, and what is still unverified |

More in the [Quick start](docs/wiki/Quick-start.md) and [FAQ](docs/wiki/FAQ.md).

## Supported harnesses

The write formats are built from each tool's documentation and are **not yet verified against live installs**; `/yardmaster doctor` says so.

| Harness | Reads history | Writes routing | Switching |
|---|---|---|---|
| GitHub Copilot in VS Code | yes | `.agents/model-router/*.model-router.yml` | Automatic |
| GitHub Copilot CLI | yes | `.github/agents/*.agent.md` and an `AGENTS.md` block | Automatic per agent |
| Claude Code | yes | `.claude/agents/ym-*.md` and a `CLAUDE.md` block | Mostly automatic |
| Codex | yes | profile files `~/.codex/ym-*.config.toml` and an `AGENTS.md` block | Partial (profile chosen at start) |

Planned, one harness per release: v1.1 Cursor and cursor-agent, v1.2 Cline, Roo and Kilo, v1.3 Gemini CLI and Qwen Code,
v1.4 OpenCode, v1.5 Aider, v1.6 Continue, v1.7 Goose, v1.8 Windsurf, Zed, JetBrains and others where a stable local store
exists. Details: [Supported harnesses](docs/wiki/Supported-harnesses.md).

## Security

- **No network of its own.** Standard library only, no third-party runtime dependency, and the test suite runs with sockets blocked.
- **Secrets are redacted before anything is sent**, and only redacted batches leave, through the AI provider your harness already uses.
- **Chat text is untrusted.** It is fenced, and the model's output must pass strict schemas before anything is written.
- **Safe writes.** Allow-listed files, marked blocks only, a diff and an approval code, a backup, and `undo`.
- **Checked.** A penetration-test suite and fuzzing run in CI; releases are reproducible and carry signed build provenance.

Read [COMPLIANCE.md](COMPLIANCE.md), [SECURITY.md](SECURITY.md), the [threat model](docs/security/threat-model.md), the
[ASVS L2 mapping](docs/security/asvs-l2.md) and the [pentest report](docs/security/pentest-report.md).

## Verify a release

```sh
sha256sum -c SHA256SUMS
gh attestation verify yardmaster-X.Y.Z.zip --repo RickCiviero/yardmaster
```

The zip is reproducible: `python tools/build_release.py X.Y.Z out/` from the tag gives the same bytes.

## Contributing

Read [Contributing](docs/wiki/Contributing.md). Run `python -m pytest -q` and `ruff check .` before you open a pull
request. Report bugs and ideas in [GitHub Issues](https://github.com/RickCiviero/yardmaster/issues). Real chat text
must never enter the repo: use `tools/make_fixture.py`. Report vulnerabilities privately, as described in
[SECURITY.md](SECURITY.md).

## Licence

[MIT](LICENSE) © 2026 RickCiviero
