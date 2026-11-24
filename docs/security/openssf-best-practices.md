# OpenSSF Best Practices badge: how to register, and the answers

Registering needs your GitHub login and a click in your browser, so only you can do it. This page gives the steps, and a
suggested answer for each criterion with a link to the evidence in this repository. Check each answer against the
question text the site shows: the wording of the criteria changes over time.

## Register (about 20 minutes)

1. Open https://www.bestpractices.dev/ and choose **Sign in** with GitHub. Approve the request in your browser. Nothing is
   sent from this repository, and the site never sees your password.
2. Choose **Add project** (or **Get your badge**). Enter `https://github.com/RickCiviero/yardmaster` and submit.
3. The site opens the **Passing** questionnaire. For each question pick *Met*, *Unmet* or *N/A*, and give the
   justification or the evidence link. The suggestions below are the starting point.
4. Save. When every required question at the Passing level is answered and met (or N/A with a reason), the badge is
   awarded. Add the markdown the site gives you to `README.md`.

Turn on two-factor authentication on your GitHub account before you sign in, if it is not on already.

## Suggested answers

### Basics

| Question (topic) | Suggested answer | Evidence |
|---|---|---|
| Project repository and website | Met: public GitHub repository | https://github.com/RickCiviero/yardmaster |
| What the project does | Met | `README.md`, first paragraphs |
| How to contribute | Met | `docs/wiki/Contributing.md` |
| Open-source licence | Met: MIT, recognised by the OSI | `LICENSE` |
| Basic usage documentation | Met | `README.md`, `docs/wiki/Quick-start.md` |
| How to report a vulnerability | Met: GitHub private vulnerability reporting, enabled | `SECURITY.md` |
| Response to vulnerability reports | Met: acknowledgement within 72 hours, fix target 30 days for high and critical issues | `SECURITY.md` |

### Change control

| Question (topic) | Suggested answer | Evidence |
|---|---|---|
| Public version control with history | Met | GitHub, `main` with signed, linear history |
| Unique version identifiers | Met: semantic versions as `v` tags | `CHANGELOG.md`; tags `v1.0.0`, `v1.1.1` (`v1.1.0` is a tag with no release, see the changelog) |
| Release notes | Met | `CHANGELOG.md`; each GitHub release has generated notes |

### Reporting

| Question (topic) | Suggested answer | Evidence |
|---|---|---|
| Bug reporting process | Met: GitHub Issues for bugs, private reporting for vulnerabilities | `README.md`, `SECURITY.md` |

### Quality

| Question (topic) | Suggested answer | Evidence |
|---|---|---|
| Working build system | Met: `pyproject.toml` builds a wheel and a source distribution; `tools/build_release.py` builds the reproducible zip | `pyproject.toml`, `tools/build_release.py`, `.github/workflows/release.yml` |
| Automated test suite | Met: over 1,400 tests, run on Windows, macOS and Linux with two Python versions | `.github/workflows/ci.yml` |
| Tests for new functionality | Met: changes arrive with tests; for example `tests/unit/test_catalog.py` covers the catalog | `tests/` |
| Warnings enabled | Met: ruff with the E, F, I, UP and B rule sets; bandit in CI at medium severity and up (bandit -ll) | `pyproject.toml`, `.github/workflows/security.yml` |
| Secure development knowledge | Your statement. The security design is documented | `docs/security/threat-model.md`, `docs/security/asvs-l2.md` |

### Security

| Question (topic) | Suggested answer | Evidence |
|---|---|---|
| Cryptography and secure connections | Met: no custom cryptography; downloads over HTTPS; Sigstore signatures and GitHub attestations | `docs/security/data-flow.md`, `COMPLIANCE.md` |
| Secure design | Met: twelve named controls, each with a test | `docs/security/threat-model.md` |
| Secure development practices | Met: penetration-test suite on three systems; fuzzing; hash-locked installs; pinned actions | `tests/pentest/`, `tests/fuzz/`, `.github/requirements/` |
| Known vulnerabilities in dependencies | Met: pip-audit in CI; Dependabot for Actions, pip and the install tools | `.github/workflows/security.yml`, `.github/dependabot.yml` |
| Static analysis | Met: CodeQL, Semgrep, Bandit and gitleaks, on every pull request | `.github/workflows/security.yml` |
| Dynamic analysis | Met: ClusterFuzzLite on every pull request; hypothesis property tests | `.github/workflows/cflite_pr.yml`, `.clusterfuzzlite/`, `tests/fuzz/` |
| Signed releases | Met: each release file has a Sigstore bundle and a build attestation | `.github/workflows/release.yml`, `COMPLIANCE.md` |
| Branch protection | Met: `main` needs 15 passing checks, linear history, signed commits, and no force pushes; `v*` tags cannot be moved or deleted | Repository settings; `docs/security/repo-hardening.md` |

## Still open

- The **Packaging** and **Contributors** parts of the OpenSSF Scorecard are separate from this badge. The Scorecard
  status is in `docs/security/asvs-l2.md`.
- After you get the badge, add its markdown to the README. The repository has no badge yet.
