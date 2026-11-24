# Security and compliance

Yardmaster reads sensitive material (your chats), so it is built to a strict bar.

| Control | In one line |
|---|---|
| S1 | Standard library only, no third-party runtime dependency |
| S2 | No network code; the whole test suite runs with sockets blocked |
| S3 | No `subprocess`, `eval`, `pickle` or shell use |
| S4 | Read-only, contained collectors with size caps |
| S5 | Secrets redacted before batching; optional `--redact-pii` |
| S6 | Chat text fenced as untrusted; model output must pass a strict schema |
| S7 | Allow-listed writes, marked blocks, diff, approval code, backup, `undo` |
| S8 | Batches in a private temp dir, deleted after the run |
| S9 | Last 30 days by default; cost and batch-count gates; `preview` shows exactly what is sent |
| S10 | Pinned CI actions, reproducible release zip, signed provenance, SBOM |
| S11 | Logs and errors never contain chat text |
| S12 | Private vulnerability reporting, documented response times |

Every control has an automated test. The full material is in the repository:

- [COMPLIANCE.md](https://github.com/RickCiviero/yardmaster/blob/main/COMPLIANCE.md): the one-pager for reviewers, including the admin `policy.toml`
- [SECURITY.md](https://github.com/RickCiviero/yardmaster/blob/main/SECURITY.md): how to report a vulnerability
- [Threat model](https://github.com/RickCiviero/yardmaster/blob/main/docs/security/threat-model.md), [ASVS L2 mapping](https://github.com/RickCiviero/yardmaster/blob/main/docs/security/asvs-l2.md), [data flow](https://github.com/RickCiviero/yardmaster/blob/main/docs/security/data-flow.md), [pentest report](https://github.com/RickCiviero/yardmaster/blob/main/docs/security/pentest-report.md)

What leaves your machine: only redacted batches, sent by your harness to the provider you already use. Redaction is best
effort; use `preview N` to see what would be sent.
