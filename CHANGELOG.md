# Changelog

All notable changes. The format follows [Keep a Changelog](https://keepachangelog.com/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.1] - 2026-11-24

### Fixed

- The 1.1.0 release run failed at its signing step: the installed cosign refuses `sign-blob` without `--bundle`. The tag `v1.1.0` is immutable, so it has no release assets. 1.1.1 is the first complete release with the 1.1.0 changes.
- Release files are signed as Sigstore bundles (`*.sigstore.json`), the format cosign writes now.

## [1.1.0] - 2026-11-24 (tag only: its release run failed at the signing step, see 1.1.1)

### Fixed

- Codex: profiles are now `~/.codex/ym-<group>.config.toml` files. Codex 0.134 and later ignore the `[profiles.*]` tables that 1.0.0 wrote. If you applied 1.0.0 Codex routing, run `/yardmaster undo`, or delete the `# yardmaster:begin` block from `config.toml`.

### Added

- `install-check` workflow: installs from each documented channel on fresh Windows, macOS and Linux runners, then runs `doctor`. The pinned tools use an integrity-hashed lock file.
- `tools/verify_release.py`: checks a downloaded release file against `SHA256SUMS`.
- The wiki sync can be started by hand.
- Release files: a wheel and a source distribution are attached to each release, built and smoke-tested in CI and signed like the zip. `pipx install <wheel URL>` runs the command without a harness. PyPI is not used: the name `yardmaster` there belongs to another project.
- Supply chain: every `pip install` in a workflow installs from a hash-locked file (`.github/requirements/`), and a test enforces it. Release files are signed with Sigstore from the next release on. ClusterFuzzLite runs a fuzz target for the verdict and plan validators on every pull request.

### Changed

- Routing no longer uses a price list. The model catalog (`models.json`, shipped inside the package) says which models each harness offers and how strong each one is. Strength is a tier: light, standard, heavy or frontier.
- The judge answers three questions for each chat: how strong the model that did the work was, the weakest tier that would have done the job, and the weakest model of that tier. The verdict field `weakest_sufficient_model` replaces `cheapest_sufficient_model`, so verdict files written for 1.0.0 must be regenerated.
- `ledger` reports fresh tokens (input plus output), shows cache reads apart, and splits the total by strength. It no longer shows dollar estimates. Copilot credits are shown as Copilot reports them.
- `survey` compares the judging's tokens with the fresh tokens spent in the range. The 10% gate is unchanged.
- Claude-Mem's own observer sessions are left out of every command by default. `--include-claude-mem` adds them back.
- The wiki's Pricing page is replaced by Models.

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
