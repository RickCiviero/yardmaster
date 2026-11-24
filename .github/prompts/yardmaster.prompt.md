---
mode: agent
description: Route each kind of AI task to the weakest model that does it well (Yardmaster)
---

Follow the instructions in the yardmaster skill's `SKILL.md` exactly, including its safety rules. Look for it at
`.github/skills/yardmaster/SKILL.md` in this repository, or `~/.copilot/skills/yardmaster/SKILL.md`.

Run the full protocol (survey, judge, validate, plan, preview, apply) over the last 30 days of chats, unless I name a
different range, a project, or one of `ledger`, `undo`, `doctor`, in which case run only that.

Never write configuration yourself and never skip my explicit approval of the diff.
