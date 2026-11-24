---
description: Route each kind of AI task to the weakest model that does it well (Yardmaster)
argument-hint: "[ledger | undo | doctor | --from YYYY-MM-DD --to YYYY-MM-DD | --project]"
---

Use the **yardmaster** skill and follow its instructions exactly, including its safety rules.

Arguments: $ARGUMENTS

- No arguments: run the full protocol (survey, judge, validate, plan, preview, apply) over the last 30 days.
- `ledger`: run only the usage report (tokens and strength). No analysis, no model judgement.
- `undo`: restore the files changed by the last applied run.
- `doctor`: run only the health check.
- Anything else (for example `--from 2026-10-01 --to 2026-10-31`, `--last`, `--project`): pass it to the survey step.

Never write configuration yourself and never skip the user's explicit approval of the diff.
