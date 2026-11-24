# Quick start

1. **Install** with one of the commands in the [README](https://github.com/RickCiviero/yardmaster#install). You need Python 3.11 or newer.
2. In your harness, say **`/yardmaster`**.
3. It runs `doctor`, then a **survey**: how many chats it found, which workspaces are included, what was redacted and what the analysis will cost. Say no, or exclude a workspace, if you need to.
4. The model you are already using judges each chat. You are shown the **manifest** (the groups and the model for each) and a **diff**.
5. Say yes to that exact diff and it is written. Say anything else and nothing is.
6. Changed your mind: **`/yardmaster undo`**.

## Other commands

| Say | Does |
|---|---|
| `/yardmaster ledger` | Tokens and credits per harness, model and strength. No analysis, no AI call |
| `/yardmaster --last` | Survey the whole previous month |
| `/yardmaster --from 2026-10-01 --to 2026-10-31` | A chosen range |
| `/yardmaster --project` | Only chats of the current project |
| `/yardmaster doctor` | What can be read and written here, and what is unverified |

By default the last 30 days of all your chats are used, and routing is written into the **current project** for the
harness you are in. `--global` writes that harness's user-level config instead.

See also [How it works](How-it-works) and the [FAQ](FAQ).
