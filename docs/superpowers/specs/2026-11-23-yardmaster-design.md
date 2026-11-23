# Yardmaster — Design

> *"Thirty years in the switchyard. I never once sent a locomotive to haul a postcard."*
> — the Yardmaster

Date: 2026-11-23 · Status: draft for owner review · Owner: RickCiviero

Calls marked **[builder call]** were made by Claude during design, not by the owner. They are proposals the owner can overturn.

---

## 1. Intent — the why

The owner routes AI-model usage by hand today:

1. Run `copilot_chats_to_md.py` (stdlib Python). It reads every GitHub Copilot chat (VS Code + Copilot CLI) in a date range and dumps the full raw content, the models used and the Copilot credits spent into one Markdown file.
2. Upload that Markdown to an M365 Copilot agent, which reads it and produces a `model-router.yml`.
3. Paste the result into `.agents/model-router/<name>.model-router.yml`, which VS Code 1.147 uses to route each request to a model automatically.

The goal is to spend AI credits as cheaply as possible without losing quality. The process is manual, works for only one harness, and sends full raw transcripts (code, paths, possibly secrets) to a third service.

**Yardmaster** turns that into one on-demand skill command. It works in every major agentic harness (not only Copilot in VS Code) and on Windows, macOS and Linux. It must be safe enough to pass a strict corporate security review.

## 2. Goals, non-goals, anti-goals

### Goals
- G1. **One command, on demand.** `/yardmaster` (or the harness's equivalent) runs collect → redact → analyse → propose → approve → write.
- G2. **Full-chat analysis by the invoking model.** The model the harness is running when the skill is invoked reads **every chat in full** (not titles or first prompts), judges which model was used, and decides the **cheapest model that would have done that job correctly**.
- G3. **Task grouping.** Chats are grouped by task kind (e.g. hard planning, running tests, writing code, bug fixing, docs, refactoring, quick questions). Groups are open-ended: seeded from that list, and the model may add more. For each group, pick the cheapest suitable model **from the models available in that harness**.
- G4. **Write the router.** Use the strongest automatic switching each harness supports. Where it supports none, write clear routing guidance into its instruction file.
- G5. **Every harness we can read.** Read history from, and write routing for, as many agent harnesses as possible (§6).
- G6. **Cross-platform.** Windows, macOS and Linux, with identical behaviour.
- G7. **Security is a hard requirement.** Secure by default, with every control tested, including a penetration-test suite in CI (§9).
- G8. **Installable the way popular skills are** (caveman, ponytail, superpowers, graphify, impeccable): plugin marketplace, `npx skills add`, harness-native extension installs (§10).
- G9. **A brand** with a persona that opens the wiki (§11).

### Non-goals
- No scheduled or automatic runs. **On demand only** (owner decision).
- No server, account, dashboard or telemetry.
- No live per-request proxy or router. Yardmaster writes config, and the harness does the routing.
- No guarantee of exact spend accounting across harnesses whose plans are flat-rate. Those get an *equivalent* API-price estimate.

### Anti-goals (would be failure even if it "works")
- Any secret leaves the machine un-redacted.
- Anything is written without the user approving a diff.
- Yardmaster edits outside its own marked block in a shared file (`CLAUDE.md`, `AGENTS.md`, …) or outside its allow-listed paths.
- Old chat content can steer what gets written (prompt injection).
- The analysis costs more than it plausibly saves. The cost estimate is shown first.
- It invents model ids the harness does not offer.
- It adds a third-party dependency to the core.

## 3. Constraints

- **Core language:** Python ≥ 3.11, **standard library only** (owner chose approach A). **[builder call]** 3.11 rather than 3.9, to get `tomllib` for safely reading Codex/Aider config. The skill must detect a missing or old Python and print exact install guidance per OS instead of failing obscurely.
- **No network access from Yardmaster code.** The only data that leaves the machine is the redacted text the harness sends to its own model.
- **The analysis model is the invoking harness model** (owner decision). No extra API keys, no extra vendor.
- **Scope:** all chats by default, and `--project` restricts to the current workspace (owner decision). Before sending anything, show the list of workspaces included, with counts, and allow excluding them.
- **VS Code router format** (from the owner's real file, VS Code 1.147):
  ```yaml
  version: 1
  description: Opus to build, GPT-6 Luna for quick questions.
  routes:
    - model: opus
      when: Building or changing code over many steps, such as a feature, a bug fix, or a refactor.
    - model: gpt-6-luna
      when: Quick answers and small chores, such as where something is or what a setting does.
  ```
- **Existing logic to keep:** the owner's script's VS Code change-log replay (`kind` 0 initial / 1 set / 2 push-splice / 3 delete), `copilotCredits` per request, CLI `accountingSnapshot.totalNanoAiu / 1e9` on the last `session.shutdown`, local-time inclusive date ranges, `--current` / `--last` / `--from` / `--to` semantics, and the VS Code / VS Code Insiders user-dir discovery on all three OSes.

## 4. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| **A** | **Python stdlib core plus a thin skill file per harness** | Grows from the owner's working script. Zero third-party dependencies, minimal supply chain, easy to audit. Needs Python ≥3.11 installed. | **Chosen by owner** |
| B | Node/TypeScript core via `npx` | Node is present for most CLIs. Means rewriting the parser, a heavier npm supply chain, and plain VS Code users may lack Node. | Rejected |
| C | Prompt-only skill (agent reads files with its own tools) | Unreliable change-log replay, huge token cost, no redaction before the model sees secrets, nothing to pentest. | Rejected: fails G7 |
| — | Go single binary | No runtime, signed binaries. A full rewrite that doesn't fit how skills install. | Fallback only if Python is blocked on target machines |

## 5. Architecture

```
          ┌──────────── harness (Copilot / Claude Code / Codex / …) ────────────┐
          │  SKILL.md  ── tells the model the protocol below                    │
          │     │                                                               │
 user ──► │  /yardmaster ─► yardmaster.py survey ──► batches/*.json (redacted)  │
          │                       ▲                         │                   │
          │   collectors/* ───────┘                         ▼                   │
          │   (read-only)                       invoking model reads batches,   │
          │                                     emits verdicts.json (schema)    │
          │                                                 │                   │
          │                    yardmaster.py validate ◄─────┘                   │
          │                                                 │                   │
          │                     model groups verdicts ─► plan.json (schema)     │
          │                                                 │                   │
          │   yardmaster.py route --dry-run ─► diff ─► user approves ─► --apply │
          │                         writers/* (allow-listed paths, marked blocks)│
          └─────────────────────────────────────────────────────────────────────┘
```

**The code is deterministic and does all file I/O. The model does only judgement.** The model never writes files directly. It produces JSON that the code validates against a strict schema and then renders.

### 5.1 Commands (CLI = `python3 <skill>/scripts/yardmaster.py`)

| Command | Does |
|---|---|
| `doctor` | Python version, detected harnesses, readable stores, write targets, permissions. Read-only. |
| `survey [--current\|--last\|--from D --to D] [--project] [--harness h,…] [--exclude-workspace …]` | Collect → normalise → redact → batch. Prints a summary (chats, workspaces, size, **estimated analysis cost**) and writes batches to a private temp dir. Default range: **last 30 days** **[builder call]**. |
| `preview <batch>` | Shows exactly what would be sent to the model. |
| `validate verdicts.json` / `validate plan.json` | Schema-checks the model output. Rejects unknown models, unknown groups, paths and anything off-schema. |
| `route --target <harness> --plan plan.json [--global] --dry-run\|--apply` | Renders the router for one harness, shows a unified diff, and on `--apply` backs up then writes atomically. |
| `ledger [range]` | Spend report (credits / tokens / estimated $) per harness, model and group. No model call needed. |
| `undo` | Restores the last backup set. |
| `export-md [range]` | Writes a Markdown archive (redacted, local), preserving the owner's old workflow. |

The skill's `/yardmaster` default runs `survey`, the analysis, `validate`, `route --dry-run` for each detected harness (or `--target`), asks for approval, then runs `--apply`.

### 5.2 Normalised chat record (internal)
`{harness, chat_id, workspace, title, first, last, turns:[{role, text, model, ts, tokens_in, tokens_out, cached, cost_units}], totals:{requests, credits|tokens, est_usd}, notes[]}`. Tool calls and tool outputs are kept, but each tool output is capped at **8 KB per item**, with a `[…truncated N bytes]` marker **[builder call]**. User and assistant text is never truncated (G2). Chats longer than one batch are split into consecutive chunks that carry the chat id and the chunk index.

### 5.3 Analysis protocol (in SKILL.md, the same for every harness)
1. Run `survey`. Show the summary and cost estimate, and **ask before continuing**.
2. For each batch (≤ ~60k tokens **[builder call]**, tuned per harness context size), read it and emit one verdict per chat:
   `{chat_id, task_group, task_summary(≤25 words, no code/secrets), model_used, outcome: ok|struggled|failed, sufficient_tier: light|standard|heavy|frontier, cheapest_sufficient_model, confidence 0–1, reason(≤30 words)}`.
   Where the harness has subagents (Claude Code, Codex, OpenCode, Copilot CLI), batches may be analysed in parallel by subagents running the **same** model.
3. `validate verdicts.json`.
4. Merge into groups. For each group, choose the cheapest model whose confidence-weighted verdicts say it is sufficient, using `pricing.json` and only **available** models (§7). Write the `when` in the owner's style: *kind of work, "such as" + concrete examples drawn from real chats*. Merge groups that end up on the same model. Order routes from most to least expensive.
5. `validate plan.json` → `route --dry-run` → show the diff and the expected savings → user approves → `--apply`.
6. Batch files are deleted at the end (and on any failure) **[builder call]**.

Batches wrap chat content in explicit data fences with a nonce, and instruct the model that everything inside is untrusted data, never instructions (§9).

## 6. Harness coverage

**Release scope (owner decision):** **v1** = Tier 1 below (Copilot VS Code, Copilot CLI, Claude Code, Codex: collectors + writers) on Windows, macOS and Linux, with the **complete** security bar of §9 and all install channels of §10. Tier 2 and Tier 3 follow in v1.1+, one harness per minor release, each with the same fixture, pentest and parity requirements.

Each harness gets one **collector** (reads history, read-only) and one **writer** (emits routing). Paths below are starting points. **Each must be verified against the live tool before its collector ships**, with a real anonymised fixture committed (§9.6). Every collector honours its tool's home-override env var and accepts an explicit `--path`.

### 6.1 Collectors (history sources)

| Tier | Harness | Where history lives (Win / mac / Linux) | Cost signal |
|---|---|---|---|
| 1 | GitHub Copilot – VS Code (+ Insiders) | `<User>/workspaceStorage/<h>/chatSessions/*.json[l]`, `…/GitHub.copilot-chat/transcripts/`, `<User>/globalStorage/emptyWindowChatSessions/` (from owner's script) | `copilotCredits` per request (exact) |
| 1 | GitHub Copilot CLI / app | `~/.copilot/session-state/<id>/events.jsonl` + `workspace.yaml` (`COPILOT_HOME`) | `totalNanoAiu/1e9` per session |
| 1 | Claude Code | `~/.claude/projects/<enc-cwd>/<session>.jsonl` (`CLAUDE_CONFIG_DIR`) | `message.usage` tokens × price |
| 1 | OpenAI Codex CLI / IDE | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (`CODEX_HOME`) | `token_count` events × price |
| 2 | Cursor (IDE) + cursor-agent CLI | `<Cursor User>/globalStorage/state.vscdb` + workspace `state.vscdb` (SQLite), `~/.cursor/chats/` | tokens if present, else estimated |
| 2 | Gemini CLI / Qwen Code | `~/.gemini/tmp/<hash>/chats/*.json`, `~/.qwen/…` | usage metadata × price |
| 2 | OpenCode | `~/.local/share/opencode/storage/…` (`XDG_DATA_HOME`) | per-message `cost` + tokens |
| 2 | Cline / Roo Code / Kilo Code | `<VSCode User>/globalStorage/<ext-id>/tasks/<id>/{ui_messages,api_conversation_history}.json` | `api_req_started` cost/tokens |
| 2 | Continue | `~/.continue/sessions/*.json` | estimated |
| 2 | Aider | `.aider.chat.history.md` per repo (discovered from known repos / `--path`) | model per session, estimated tokens |
| 2 | Goose | `~/.local/share/goose/sessions/` (jsonl or `sessions.db`) | tokens if present |
| 3 | Windsurf, Zed, JetBrains AI/Junie, Amp, Kiro, Augment, Warp, Trae | Local stores are proprietary, encrypted or server-side | **Investigate.** Ship only if a stable, readable local store exists. Otherwise list as "routing only" in `doctor`. |

SQLite stores are opened **read-only and immutable** (`file:…?mode=ro&immutable=1`) so a running editor is never locked or modified.

### 6.2 Writers (routing targets)

Each writer only touches allow-listed paths. In shared instruction files it edits **only** a `<!-- yardmaster:begin v1 -->…<!-- yardmaster:end -->` block (or `# yardmaster:begin` for TOML/YAML).

| Harness | Output (project / `--global`) | Switching |
|---|---|---|
| Copilot – VS Code | `.agents/model-router/<name>.model-router.yml` (owner format, `<name>` default `yardmaster`) | **Automatic** |
| Copilot CLI | `.github/agents/<group>.agent.md` with `model:` front-matter + `AGENTS.md` block | Automatic per agent |
| Claude Code | `.claude/agents/ym-<group>.md` (`model: haiku\|sonnet\|opus`) + `CLAUDE.md` block telling the main agent to delegate each group | Mostly automatic |
| Codex | `[profiles.ym-<group>]` in `.codex/config.toml` / `~/.codex/config.toml` + `AGENTS.md` block | Partial (profile chosen at start) |
| OpenCode | `.opencode/agent/ym-<group>.md` with `model:` | Automatic per agent |
| Roo / Kilo | `.roomodes` / `.kilocodemodes` custom modes + block in rules | Semi-automatic (sticky model per mode) |
| Aider | `.aider.conf.yml` `model` / `editor-model` / `weak-model` | Automatic by role |
| Continue | `config.yaml` model `roles` | Automatic by role |
| Goose | lead/worker model settings | Automatic (lead/worker) |
| Cursor, Windsurf, Cline, Gemini CLI, Zed, Kiro, JetBrains, others | Block in `.cursor/rules/yardmaster.mdc`, `.windsurf/rules/`, `.clinerules/`, `GEMINI.md`, etc. | Guidance |

YAML and TOML are emitted by tiny purpose-built emitters that quote every scalar. Existing TOML is read with `tomllib` to detect conflicts, and is never rewritten outside the marked block.

## 7. Prices and available models

- `pricing.json` ships with each release. It is per harness, with Copilot credit multipliers and per-token API prices (input / output / cached), carries a `as_of` date, and is covered by the release signature. A user override lives at `<config>/yardmaster/pricing.local.json`.
- **Available models** for a harness = **every model that harness offers** in `pricing.json` (owner decision: consider all models, not only the ones already used), minus the user deny-list in `<config>/yardmaster/config.toml` and the admin policy (§13b).
- **Cross-harness pooling (owner decision).** Task groups are built from the chats of all harnesses together. Every model in `pricing.json` carries a capability tier (`light` / `standard` / `heavy` / `frontier`) and per-skill notes (e.g. long-context, tool use). Verdicts record the tier that was sufficient. Each harness's router then picks the cheapest available model of that tier in **that** harness. So a harness with little or no history still gets a full router.
- `validate` rejects any model id that is not available for that harness (anti-goal: invented ids).
- Flat-rate plans (Claude Pro/Max, ChatGPT plans) are reported as *equivalent API cost* and ranked by price tier, plus a rate-limit weight, since the real saving is quota.

## 8. User experience

- `/yardmaster` → summary card → "Analyse 214 chats (3.1 MB → ~410k tokens, est. 1.6 credits)? [y/N]" → progress per batch → proposed groups table (group · chats · model used most · proposed model · est. saving) → per-file diffs → "Apply? [y/N]".
- Plain outputs, in the Yardmaster voice only in headings and one-liners (§11). Never in the files it writes.
- Every run leaves `~/.local/state/yardmaster/runs/<ts>/` (or the platform equivalent), containing a `report.md` with no chat content: groups, models, savings, files changed, and backup locations.

## 9. Security

Target: **OWASP ASVS 4.0 Level 2** controls applicable to a local CLI, **OpenSSF Best Practices (passing → silver)**, **OpenSSF Scorecard ≥ 8**, **SLSA Build L3** provenance on releases. Every control below has at least one automated test.

### 9.1 Threat model (STRIDE, maintained in `docs/security/threat-model.md`)
Assets: chat content, secrets inside it, user config files, the integrity of routing decisions. Adversaries: (a) malicious text inside old chats (prompt injection), (b) malicious or corrupt history files (parser attacks), (c) other local users or processes (temp-file races), (d) supply chain (a tampered release or pricing file), (e) a confused or compromised model output.

### 9.2 Controls
| # | Control |
|---|---|
| S1 | **Zero third-party runtime deps**, stdlib only. A CI check fails if any `import` falls outside the stdlib allow-list. |
| S2 | **No network.** No `socket`/`urllib.request`/`http` use. A CI test runs the full suite with sockets monkey-patched to raise. |
| S3 | **No code execution surface.** No `subprocess`, `os.system`, `eval`, `exec`, `pickle`, `marshal`, `yaml.load`, `shell=True`. Enforced by Semgrep and Bandit rules. |
| S4 | **Read-only collectors.** Files are opened read-only, SQLite `mode=ro&immutable=1`, nothing is followed outside the expected roots (resolved-path containment check), symlinks are not followed for writes, and per-file (default 200 MB) and per-line size caps defend against memory DoS. |
| S5 | **Redaction before batching.** Rules ported from the gitleaks default ruleset (cloud keys, GitHub/GitLab/Slack/Stripe tokens, JWTs, private-key blocks, connection strings, `password=` assignments, bearer headers) plus a Shannon-entropy detector for long tokens. Optional `--redact-pii` (emails, IPs, usernames in paths → `~`). Redactions are counted per type and shown. **All regexes are linear-time** (no nested quantifiers, a ReDoS test corpus, a per-line length cap before matching). |
| S6 | **Prompt-injection containment.** Chat text is fenced with a random nonce and labelled untrusted. The model may only output schema JSON. `validate` enforces types, lengths, enums, an allow-listed model id per harness, no paths or URLs or code fences in free-text fields, and max sizes. Writers render from validated fields only, and free text is escaped for the target format. |
| S7 | **Safe writes.** Allow-listed target paths per writer, resolved and contained in the project root or the harness config dir. Refuses symlinked targets. Diff + explicit approval. Backup before write. Atomic replace (`os.replace` from a same-dir temp file). Edits only inside the marked block. Preserves the original line endings and encoding. `undo` restores. |
| S8 | **Private temp data.** Batches go in a `tempfile.mkdtemp()` dir with mode 0700 (POSIX) or an owner-only ACL (Windows), and are deleted in `finally`. Nothing is written to world-readable locations. Run reports contain no chat content. |
| S9 | **Least data.** The default range is 30 days. Workspace exclusion and `--project` are available. `preview` shows exactly what is sent. A max-batch-count guard needs explicit confirmation. |
| S10 | **Supply chain.** Releases are built in GitHub Actions with pinned-SHA actions, least-privilege `permissions:`, and `persist-credentials: false`. SLSA provenance plus Sigstore signatures (GitHub artifact attestations). `SHA256SUMS`. A CycloneDX SBOM. `pricing.json` is inside the signed bundle. Branch protection, signed tags, Dependabot for Actions, and CodeQL + Semgrep + Bandit + gitleaks + OpenSSF Scorecard workflows. |
| S11 | **Logging hygiene.** Logs and errors never print chat text or secrets, only ids, counts and paths. Exceptions are caught at the boundary with a safe message. `--debug` still redacts. |
| S12 | **Disclosure.** `SECURITY.md` with a private advisory channel and response SLA, `docs/security/` with the threat model, ASVS mapping, data-flow diagram and pentest report. A `COMPLIANCE.md` one-pager for corporate reviewers (data flow, what leaves the machine, controls, how to verify signatures). |

### 9.3 Penetration-test suite (`tests/pentest/`, runs in CI on all 3 OSes)
- **Path traversal / symlink escape:** history dirs containing `../`, absolute paths, symlinks and junctions (Windows) pointing outside. Write targets that are symlinks → must refuse.
- **Hostile history files:** huge lines, deep JSON nesting (recursion bomb), invalid UTF-8, NUL bytes, 2 GB sparse files, zip-bomb-like repetition, SQLite with malicious schema / triggers (read-only immutable must neutralise them), JSONL with change-log ops pointing to absurd indices.
- **Prompt injection corpus:** chats containing "ignore previous instructions", fake `</data>` fences, fake schema JSON, instructions to write to `~/.ssh`, `../../.bashrc` or `.git/hooks`, and model-id spoofing. Each must produce either a valid, harmless plan or a validation failure.
- **Malicious model output:** `plan.json` with path fields, YAML/TOML injection payloads (`\n`, `: `, `#`, `]]`, anchors, `!!python/object`), Markdown that closes the marker block, oversized fields, unknown models. All must be rejected or safely escaped. Includes a round-trip test that the parsed output equals the intended structure.
- **Secret leakage:** a seeded corpus of real-format fake secrets (gitleaks test fixtures). Assert 0 leak into batches, logs, reports or written files.
- **ReDoS:** every redaction regex is timed against adversarial strings (must stay linear).
- **Temp-file safety:** permission assertions, cleanup on SIGINT / exceptions, no predictable names.
- **Race / TOCTOU:** the target is replaced by a symlink between diff and apply. The apply must detect this, via a pre-write hash and type check, and abort.
- **Fuzzing:** `atheris` (dev-only dependency) or a stdlib property-based fuzz loop over every collector parser and the validators. A nightly CI job and a short job on each PR.
- **Static/dynamic scanning:** CodeQL, Semgrep (custom rules for S2/S3), Bandit, gitleaks on the repo, pip-audit on the dev deps.
- The report is generated into `docs/security/pentest-report.md` on each release, with a pass/fail per case.

### 9.4 Data flow statement (for COMPLIANCE.md)
Local history files → (read-only) Yardmaster → redacted batches in a private temp dir → the **same AI provider the user's harness already uses**, through that harness → JSON verdicts → local validation → local config files. No other egress exists, and none is possible from Yardmaster code (S2).

### 9.5 Out of scope
Protection against the harness's own model provider, which is already trusted by the user's choice. Protecting the user from an already-compromised local account.

### 9.6 Fixtures
Every collector ships with anonymised real-format fixtures. They are generated by a `tools/make_fixture.py` that redacts and rewrites ids, so no real chat text enters the repo. A pre-commit gitleaks hook enforces this.

## 10. Distribution and install

The skill directory is self-contained: `skills/yardmaster/SKILL.md` plus `scripts/yardmaster/` (the package) plus `pricing.json`. **No pip install is needed**: the skill runs `python3 <skill_dir>/scripts/yardmaster.py`.

| Channel | Command |
|---|---|
| Claude Code plugin marketplace | `/plugin marketplace add RickCiviero/yardmaster` → `/plugin install yardmaster@yardmaster` |
| Universal skills installer (many agents) | `npx skills add RickCiviero/yardmaster` |
| Codex | Plugin / skills dir (`~/.codex/skills/yardmaster`), via `npx skills add … -a codex` or manual copy |
| GitHub Copilot (VS Code / CLI) | Agent skills dir (`.github/skills/` or `~/.copilot/skills/`), Copilot CLI `/plugin install` |
| Gemini CLI | `gemini extensions install https://github.com/RickCiviero/yardmaster` |
| Cursor / Windsurf / Cline / others | `npx skills add` target, or manual copy into the tool's skills/rules dir, as documented per tool |
| Verify | `gh attestation verify` / `cosign verify-blob` + `SHA256SUMS` instructions in README |

Manifests: `.claude-plugin/plugin.json` + `marketplace.json`, `gemini-extension.json`, Codex plugin manifest, `skills/yardmaster/SKILL.md` with front-matter that is portable across harnesses. Slash-command / prompt files where the harness supports them (`/yardmaster`, `/yardmaster ledger`, `/yardmaster undo`).

## 11. Brand

- **Name:** **Yardmaster**, the railway official who runs the switchyard and decides which track every car goes down. The name was free on npm at the time of writing. Check PyPI and GitHub before creating the repo. **[builder call]**
- **Persona (opens the wiki and README):** *The Yardmaster.* Thirty years in the switchyard. A quiet, unhurried veteran in a worn cap with a pocket watch. Has seen every kind of freight. Sends each job down the cheapest track that still gets it there on time. Never sends a locomotive to haul a postcard, never sends a handcar up a mountain. Keeps a ledger of every fare. Doesn't trust anyone who can't show their manifest (security).
- **Tagline:** *Right job. Right track. Lowest fare.*
- **Vocabulary** (light touch, UI only): `survey` (read the yard), `manifest` (the plan), `switch` / `route` (write config), `ledger` (spend report), `signal` (approval prompt). Signals: green = cheaper model fine, amber = keep current, red = needs a stronger model.
- **Visual:** a railway semaphore signal / switch-points mark. Palette: signal red `#C8102E`, amber `#F2A900`, green `#1E8E3E`, iron `#2B2D31`, paper `#F4F1EA`. Mono headings. An SVG logo is generated in the repo (`assets/`).
- **Wiki pages:** Meet the Yardmaster · Quick start · How it works · Supported harnesses · Security & compliance · Pricing table · FAQ · Contributing.

## 12. Repository layout

```
yardmaster/
  README.md  SECURITY.md  COMPLIANCE.md  LICENSE (MIT [builder call])  CHANGELOG.md
  .claude-plugin/{plugin.json,marketplace.json}  gemini-extension.json  …manifests
  skills/yardmaster/
    SKILL.md
    pricing.json
    scripts/yardmaster.py            # entry point
    scripts/yardmaster/{cli,model,redact,batch,schema,validate,diff,io_safe,pricing}.py
    scripts/yardmaster/collectors/{vscode_copilot,copilot_cli,claude_code,codex,cursor,gemini,opencode,cline_family,continue_,aider,goose}.py
    scripts/yardmaster/writers/{vscode_router,copilot_cli,claude_code,codex,opencode,roo_kilo,aider,continue_,goose,guidance}.py
  commands/ (per-harness slash-command wrappers)
  tests/{unit,collectors,writers,e2e,pentest,fixtures}/
  docs/{superpowers/specs,superpowers/plans,security,wiki}/
  assets/ (logo, palette)
  .github/workflows/{ci,codeql,scorecard,release,fuzz}.yml
```

## 13. Decisions log

| Decision | By |
|---|---|
| Full chats are read by an AI model, which judges the cheapest sufficient model, groups by task and picks a model per group | Owner |
| The analysis model is the harness model active when the skill is invoked | Owner |
| Switch automatically where the tool allows, guidance where it doesn't | Owner |
| VS Code router YAML format (as given) | Owner |
| On demand only | Owner |
| All chats by default, `--project` on request | Owner |
| Security as a hard requirement, no specific framework → strict generic bar | Owner |
| Approach A: Python stdlib core plus a thin skill per harness | Owner |
| v1 = Copilot (VS Code + CLI), Claude Code, Codex on Win/mac/Linux with the full security bar. Other harnesses in v1.1+ | Owner |
| Consider all models each harness offers. Pool task groups across harnesses via capability tiers | Owner |
| Public GitHub repo with a licence | Owner |
| Python ≥3.11, last-30-days default, 8 KB tool-output cap, ~60k-token batches, delete batches after run, MIT licence, name/brand | Builder call |

## 13b. Builder-check resolutions

- **Who enforces approval [builder call].** The model cannot be the only gate, because it has just read untrusted text. Three layers:
  1. The skill ships **without** pre-approving `route --apply` in any harness's allowed-tools list, so the harness's own permission prompt shows the human the exact command.
  2. `route --dry-run` stores the rendered output plus the hash of every target file under a run id. `route --apply <run-id>` writes **only** that stored, already-validated output, and aborts if any target changed since the dry run.
  3. When a TTY is available (terminal harnesses), `--apply` also asks `Type the 4-letter code shown in the diff`. In harnesses without a TTY, layer 1 is the gate, and `COMPLIANCE.md` says so plainly.

  Even a fully hijacked model can therefore only write a schema-valid router into allow-listed paths, with a backup and `undo`.
- **Owner's script [answered].** The scanned source was read during design. It is transcribed into `reference/copilot_chats_to_md.py` in the repo as the behavioural reference, and Tier-1 Copilot collectors must reproduce its numbers on the same fixtures (a parity test).
- **Default write location [builder call].** Routing is written for the harness the skill is running in, into the **current project**. `--global` writes that harness's user-level config. `--target all` writes every detected harness, still only into the current project. Yardmaster never writes into other analysed workspaces.
- **Windows temp-dir ACL [builder call].** No `ctypes`. Batches go under the per-user temp dir (`%LOCALAPPDATA%\Temp`, which Windows ACLs to the user by default). The code asserts the dir is inside the user profile and refuses otherwise. A pentest case checks it.
- **Cost gate [builder call].** Before analysis, `survey` shows the estimated analysis cost next to the spend `ledger` found for the same range. If the estimate is above 10% of that spend, it warns and needs an explicit `--yes-expensive`. No savings forecast is made beforehand.
- **Admin policy [builder call].** Optional `policy.toml` at `%ProgramData%\yardmaster\`, `/Library/Application Support/yardmaster/` or `/etc/yardmaster/`. Policy wins over user config. User config can only narrow it (fewer models, fewer harnesses, more redaction), never widen it. `doctor` shows the effective policy and where each value comes from.

## 14. Left to the builder
- Exact on-disk formats per harness, verified against current versions, with fixtures.
- Batch size tuning per harness context window.
- Exact redaction rule list (port the gitleaks defaults and keep them in sync).
- Wording of SKILL.md prompts and the per-harness wrappers.
- Logo artwork within the brand spec.
- Choice of `atheris` vs stdlib fuzz loop.
