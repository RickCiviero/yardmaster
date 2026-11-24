# Yardmaster: compliance summary for reviewers

One page for a security or procurement review. Detail lives in [`docs/security/`](docs/security/).

## What it is

A skill (plus a stdlib-only Python CLI) that reads the chat history your AI harnesses already keep, works out which
model suits each kind of task, and, after you approve a diff, writes a small marked routing block into your config files.

## What it reads

Local history files of Claude Code, Codex, GitHub Copilot CLI and GitHub Copilot in VS Code, opened **read-only**
(SQLite as `mode=ro`). Nothing outside the harness history roots is read. Symlinks are not followed, and oversized files
and lines are skipped. `--project` and `--exclude-workspace` narrow it; the default range is 30 days.

## What leaves the machine

**Only redacted batches, sent by your own harness to the AI provider you already use.** Yardmaster has no network code,
no telemetry, no update check and no account. `preview N` prints batch N exactly as it would be sent, and a cost gate and
a batch-count guard need your explicit confirmation. Secrets (cloud keys, tokens, JWTs, private keys, connection
strings, `password=` assignments, high-entropy strings) are redacted before batching; `--redact-pii` adds emails, IPs
and home paths. Redaction is best effort (see the threat model's residual risk).

## What it writes

| Where | What | Guard |
|---|---|---|
| A private temp directory (or `--out`) | Redacted batches | Owner-only, deleted after the run or by `clean` |
| The state directory | A run record (the diff and hashes, no chat text) | Mode 0600 |
| The target config files | One marked block per file | Diff first, approval code, backup, hash re-check, atomic replace, `undo` |
| `export-md` output | A redacted Markdown archive you asked for | Refuses to overwrite, and refuses inside a git repo without `--force` |

## Controls

S1 stdlib only, no third-party runtime dependency. S2 no network. S3 no code-execution surface. S4 read-only,
contained collectors. S5 redaction before batching. S6 prompt-injection containment and strict output schema. S7 safe,
reversible writes. S8 private temp data. S9 least data and gates. S10 supply chain. S11 logging hygiene.
S12 disclosure. Every control has an automated test; the table is in
[`threat-model.md`](docs/security/threat-model.md). The OWASP ASVS 4.0.3 L2 mapping is in
[`asvs-l2.md`](docs/security/asvs-l2.md), and the last penetration-test run in
[`pentest-report.md`](docs/security/pentest-report.md).

## Verify a release

Download `yardmaster-X.Y.Z.zip`, `SHA256SUMS` and `sbom.cdx.json` from the GitHub release.

```sh
sha256sum -c SHA256SUMS                                   # the zip matches the published checksum
gh attestation verify yardmaster-X.Y.Z.zip --repo RickCiviero/yardmaster   # signed provenance (Sigstore, SLSA)
cosign verify-blob --bundle yardmaster-X.Y.Z.zip.sigstore.json --certificate-identity-regexp 'https://github.com/RickCiviero/yardmaster/.github/workflows/release.yml@refs/tags/v.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com yardmaster-X.Y.Z.zip   # the release signature
```

The zip is **reproducible**: from a checkout of the tag, `python tools/build_release.py X.Y.Z out/` produces the same
bytes, so you can rebuild and compare. It contains the skill folder and the licence, nothing else.

## Admin policy (optional)

An administrator can narrow what users may do. The user's own `config.toml` can only narrow further, never widen. The
file is read from a fixed path; no environment variable can redirect it.

| OS | Path |
|---|---|
| Windows | `%ProgramData%\yardmaster\policy.toml` |
| macOS | `/Library/Application Support/yardmaster/policy.toml` |
| Linux | `/etc/yardmaster/policy.toml` |

```toml
# Never route to these models, even if the user asks.
deny_models = ["gpt-evil-1"]
# Only these harnesses may be surveyed.
harnesses = ["claude-code", "codex"]
# Always redact emails, IPs and home paths.
redact_pii = true
# Refuse runs that would need more batches than this.
max_batches = 20
```

An unreadable or invalid policy file makes Yardmaster stop rather than ignore it. `yardmaster doctor` shows the
effective setting and whether it came from the policy, the config or the default.

## Run the penetration-test suite locally

```sh
python -m pytest -m pentest -q
python -m pytest tests/fuzz -q
python tools/pentest_report.py          # writes docs/security/pentest-report.md
FUZZ_EXAMPLES=20000 python -m pytest tests/fuzz -q    # the nightly depth
```

Static scanners (CodeQL, Semgrep, Bandit, gitleaks, pip-audit, OpenSSF Scorecard) run in GitHub Actions only.

## Reporting a vulnerability

See [`SECURITY.md`](SECURITY.md).
