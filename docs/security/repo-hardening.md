# Repository hardening (one-time, by the repository owner)

These are GitHub **settings**, not files, so they cannot ship in the repo. They are deliberately not applied
automatically: they change a shared repository, and the required status checks below only exist after CI has run once
on `main`. Run them as the owner (`gh auth login` first), then record the date in `docs/security/asvs-l2.md`.

## 1. Private vulnerability reporting (needed by `SECURITY.md`)

```sh
gh api -X PUT repos/RickCiviero/yardmaster/private-vulnerability-reporting
```

## 2. Secret scanning and push protection

```sh
gh api -X PATCH repos/RickCiviero/yardmaster \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled'
```

## 3. Protect `main`

Required checks are the job names from `ci.yml` and `security.yml`. Adjust `required_approving_review_count` to `0`
for a solo maintainer (GitHub does not let an author approve their own pull request); keep everything else.

```sh
cat > protection.json <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "test (ubuntu-latest, 3.11)", "test (windows-latest, 3.11)", "test (macos-latest, 3.11)",
      "test (ubuntu-latest, 3.13)", "test (windows-latest, 3.13)", "test (macos-latest, 3.13)",
      "codeql", "semgrep", "bandit", "gitleaks", "audit", "runtime-rules",
      "pentest (ubuntu-latest)", "pentest (windows-latest)", "pentest (macos-latest)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 0, "dismiss_stale_reviews": true},
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
EOF
gh api -X PUT repos/RickCiviero/yardmaster/branches/main/protection --input protection.json
gh api -X POST repos/RickCiviero/yardmaster/branches/main/protection/required_signatures   # signed commits
```

## 4. Protect release tags

Create a ruleset so only the owner can create or move `v*` tags (Settings, Rules, Rulesets, new tag ruleset, target
`v*`, restrict creations, updates and deletions). Releases are built by `release.yml` from such a tag, so a protected tag
is what makes the signed attestation mean "this exact commit".

## 5. Verify

`gh api repos/RickCiviero/yardmaster/branches/main/protection --jq '.required_status_checks.contexts | length'` should
print `15`. The OpenSSF Scorecard workflow reports the rest; any check below 8 is listed with its reason in
`asvs-l2.md`.
