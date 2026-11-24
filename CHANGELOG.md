# Changelog

All notable changes. The format follows [Keep a Changelog](https://keepachangelog.com/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Codex: profiles are now `~/.codex/ym-<group>.config.toml` files. Codex 0.134 and later ignore the `[profiles.*]` tables that 1.0.0 wrote. If you applied 1.0.0 Codex routing, run `/yardmaster undo`, or delete the `# yardmaster:begin` block from `config.toml`.

### Added

- `install-check` workflow: installs from each documented channel on fresh Windows, macOS and Linux runners, then runs `doctor`. The pinned tools use an integrity-hashed lock file.
- `tools/verify_release.py`: checks a downloaded release file against `SHA256SUMS`.
- The wiki sync can be started by hand.
- Supply chain: every `pip install` in a workflow installs from a hash-locked file (`.github/requirements/`), and a test enforces it. Release files are signed with Sigstore from the next release on. ClusterFuzzLite runs a fuzz target for the verdict and plan validators on every pull request.

## [1.0.0] - 2026-11-24

- Collectors for GitHub Copilot in VS Code, GitHub Copilot CLI, Claude Code and Codex, read-only.
- Writers for the same four harnesses: marked blocks only, diff and approval code, backup, `undo`.
- Redaction before batching, prompt-injection containment, strict schemas for the model's output.
- Spend `ledger`, `export-md`, `doctor`, and an optional admin `policy.toml`.
- Skill, plugin and extension manifests for Claude Code, Copilot, Codex and Gemini CLI.
- Penetration-test suite, fuzzing, and a generated pentest report.
- CI: pinned actions, CodeQL, Semgrep, Bandit, gitleaks, pip-audit, Scorecard.
- Reproducible, attested release zip with `SHA256SUMS` and a CycloneDX SBOM.
- Security documents: threat model, ASVS 4.0.3 L2 mapping, data flow, `COMPLIANCE.md`, `SECURITY.md`.
- README, wiki pages and the logo.

Known limits: the write formats are not yet verified against live installs of each harness, and `pricing.json` holds
estimates (`verified` is false). The tag is not GPG-signed; the release zip carries a Sigstore build attestation instead.
