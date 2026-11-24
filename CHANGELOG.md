# Changelog

All notable changes. The format follows [Keep a Changelog](https://keepachangelog.com/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### 1.0.0 (not yet tagged)

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

Known limits at this point: the write formats are not yet verified against live installs of each harness, `pricing.json`
holds estimates (`verified` is false), and the CI scanners have not yet run on GitHub.
