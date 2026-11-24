# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x (latest release) | Yes |
| Anything older | No. Please upgrade to the latest 1.x |

## Reporting a vulnerability

**Please do not open a public issue.** Use GitHub's private vulnerability reporting:

1. Go to https://github.com/RickCiviero/yardmaster/security/advisories/new
2. Describe what you found, how to reproduce it, and which version and operating system.

Please do not include real chat content or real secrets in a report. A synthetic example is enough.

## What to expect

| Step | Target |
|---|---|
| Acknowledgement | within **72 hours** |
| Fix or mitigation for a **high or critical** issue | within **30 days** of the report being confirmed |
| Lower severity | in the next regular release |
| Disclosure | coordinated with you, through a GitHub security advisory, after a fixed release exists. Credit is given unless you prefer otherwise |

This is a one-maintainer project, so these are targets, not a contract. If a target will be missed, you will be told why.

## Scope

In scope:

- Yardmaster's code in `skills/yardmaster/` and the release zip built from it.
- Anything that lets text in a chat history, a history file, or a model output cause a write outside the marked block,
  a write outside the project or harness config directory, command execution, network access, or a secret reaching a
  batch, log, report or written file.
- Weaknesses in the release pipeline that could let a tampered release verify as genuine.

Out of scope:

- The AI provider behind your harness, or the harness itself. Report those to their vendors.
- An attacker who already controls your local account.
- A secret format that no redaction rule matches yet, unless it is a well-known credential format. Please do report
  those as ordinary issues, with a synthetic example, so a rule can be added.
- Findings that need `--force`, `--overwrite`, or a hand-edited run record on a machine you do not control.

## How the project defends itself

See [`COMPLIANCE.md`](COMPLIANCE.md) for the summary, [`docs/security/threat-model.md`](docs/security/threat-model.md)
for the threats, each with the test that proves its control, and
[`docs/security/pentest-report.md`](docs/security/pentest-report.md) for the last penetration-test run.
