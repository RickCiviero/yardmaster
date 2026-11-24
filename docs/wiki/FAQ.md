# FAQ

**Does it send my chats anywhere new?** No. Redacted batches go to the model your harness already uses, through that
harness. Yardmaster has no network code.

**What does the judging cost?** The survey shows the fresh tokens spent in the range (input plus output) and the tokens
the judging will use. If the judging would use more than 10% of the tokens spent, it asks for `--yes-expensive`.
See [Models](Models).

**Can it miss a secret?** Redaction is best effort. A secret in an unusual format can pass. Use `preview N` or
`--redact-pii`, and exclude sensitive workspaces.

**Will it overwrite my config?** It edits only a marked block, after you approve the exact diff, with a backup.
`/yardmaster undo` restores it, and refuses if you edited the file afterwards.

**Why did it say a format is unverified?** The writers are not yet checked against live installs. See [Supported harnesses](Supported-harnesses).

**Can my admin restrict it?** Yes, with a `policy.toml` that can deny models or harnesses and force PII redaction. Users can only narrow it further.

**Windows, macOS, Linux?** All three, Python 3.11 or newer.

**Which harnesses are next?** See the roadmap on [Supported harnesses](Supported-harnesses).
