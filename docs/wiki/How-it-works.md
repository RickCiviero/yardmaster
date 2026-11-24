# How it works

```
history files --read-only--> redact --> batches (private temp dir) --> your model, via your harness
                                                                              |
config files <--diff + your approval-- validate (strict schema) <-- JSON verdicts
```

1. **Survey.** Collectors read each harness's history, read-only, inside its expected folder. Secrets are redacted, long tool output is capped, and the chats are packed into batches of roughly 60,000 tokens.
2. **Judge.** For each chat, the model you are using says what kind of work it was and the lowest tier that would have done it correctly. It sees chat text only as fenced, untrusted data.
3. **Validate.** The verdicts must match a strict schema: known models for that chat's harness, short plain text, no paths, URLs or code.
4. **Plan.** Chats are grouped by kind of work. A group gets the lowest tier that at least 80% of its confidence-weighted verdicts say would suffice.
5. **Preview.** `route --dry-run` renders every file, records each target's hash, and shows the diff with an approval code. Nothing is written.
6. **Apply.** Only after your yes: the stored text is written if no target changed since the preview, with a backup. `undo` restores it.
7. **Clean.** The batches, which hold redacted chat text, are deleted.

The Python tool does all file access; the model does judgement only.

More: [Security and compliance](Security-and-compliance), [Supported harnesses](Supported-harnesses).
