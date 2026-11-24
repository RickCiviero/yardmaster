# OWASP ASVS 4.0.3 Level 2 mapping

Scope: chapters **V1, V5, V7, V8, V10, V12 and V14**. Yardmaster is a local command-line tool and a skill file. It has no
server, no web interface, no accounts, no sessions and no network code, so most of the web-facing rows are *N/A*.

How to read a row:

- **met**: a control (S1 to S12, see `threat-model.md`) implements it, and the cited `file::test` proves it.
- **met (doc)**: a process or documentation requirement, satisfied by a file in this repository (named in the row).
- **partial**: met in part. The gap is stated and accepted.
- **N/A**: the requirement does not apply. The reason is stated. No row is left blank.

Each cited test is checked by `tests/unit/test_docs_links.py`, so a renamed or deleted test breaks the build.

> **Honesty note.** The requirement text is paraphrased, and the numbering is written from ASVS 4.0.3 as the author
> knows it. Before using this file in an audit, diff the IDs and levels against the official ASVS 4.0.3 CSV
> (https://github.com/OWASP/ASVS). This is a self-assessment by the maintainer, not a third-party attestation.
> Items that run only on GitHub (CodeQL, Semgrep, Bandit, gitleaks, Scorecard, branch protection) are described, not
> proven here, until the first CI run and the steps in `repo-hardening.md` are done.

## V1 Architecture, design and threat modelling

| ID | Requirement (paraphrased) | Status | Evidence |
|---|---|---|---|
| 1.1.1 | Secure SDLC addresses security in every stage | met (doc) | Design spec section 9, plan Tasks 19 to 21, CI in `.github/workflows/` |
| 1.1.2 | Threat modelling for every design change | met (doc) | `docs/security/threat-model.md` |
| 1.1.3 | User stories include functional security constraints | met (doc) | The S1 to S12 control table in the design spec |
| 1.1.4 | Trust boundaries, components and data flows documented | met (doc) | `docs/security/data-flow.md` |
| 1.1.5 | High-level architecture and connections to remote services defined | met (doc) | `data-flow.md`; the only remote service is the user's own harness provider |
| 1.1.6 | Centralised, simple, vetted security controls | met | S5, S6, S7 each live in one module: `tests/unit/test_redact.py::test_rules_are_compiled_patterns_with_unique_names`, `tests/unit/test_safe_io.py::test_contained_rejects_dotdot_and_abs` |
| 1.1.7 | Secure coding checklist and security-aware team | met (doc) | Semgrep ban rules (`.semgrep/yardmaster.yml`), `tests/unit/test_workflows.py::test_semgrep_rules_are_well_formed_and_cover_the_bans` |
| 1.2.1 | Unique low-privilege OS account per component | N/A | One user-level CLI; it never needs elevated rights and refuses to write outside the project or harness config directory: `tests/writers/test_writers.py::test_writers_stay_inside_their_roots` |
| 1.2.2 | Communication between components is authenticated | N/A | No inter-component communication; the harness runs the CLI as a child process |
| 1.2.3 | One vetted authentication mechanism | N/A | No authentication (local CLI) |
| 1.2.4 | All authentication paths are equally strong | N/A | No authentication |
| 1.4.1 | Access control enforced at trusted enforcement points | met | Containment and approval are enforced in the CLI, not in the skill text: `tests/unit/test_route.py::test_wrong_code_always_aborts_even_without_tty` |
| 1.4.4 | One well-vetted access-control mechanism | met | One containment function: `tests/unit/test_safe_io.py::test_atomic_write_rejects_path_outside_root` |
| 1.4.5 | Attribute or feature-based access control | N/A | No users or roles; admin `policy.toml` narrows what is allowed: `tests/unit/test_settings.py::test_policy_user_cannot_widen` |
| 1.5.1 | Input and output requirements stated | met (doc) | `skills/yardmaster/SKILL.md`, schema in `tests/unit/test_schema.py` |
| 1.5.2 | Untrusted data is never deserialised with unsafe parsers | met | JSON and TOML only: `tests/unit/test_stdlib_only.py::test_planted_violations_are_caught` |
| 1.5.3 | Input validation at a trusted layer | met | `tests/unit/test_schema.py::test_shape_errors` |
| 1.5.4 | Output encoding close to the interpreter | met | `tests/unit/test_emit.py::test_yaml_roundtrip_hostile`, `tests/unit/test_emit.py::test_toml_roundtrip_hostile` |
| 1.6.1 | Cryptographic key management policy | N/A | No cryptographic keys are held; release signing is keyless (Sigstore) |
| 1.6.2 | Services use a key vault | N/A | No keys |
| 1.6.3 | Keys and passwords replaceable | N/A | No keys |
| 1.6.4 | Client-side secrets are treated as exposed | N/A | No client-side secrets; none are shipped: `tests/unit/test_workflows.py::test_gitleaks_config_extends_the_defaults` |
| 1.7.1 | Common log format | N/A | No log service; the CLI prints ids, counts and paths only (see 7.1.1) |
| 1.7.2 | Logs go to a central system | N/A | Local CLI |
| 1.8.1 | Sensitive data classified and protected | met | Chat text and secrets are the sensitive classes: `tests/unit/test_batch.py::test_redaction_counts_reported_and_secret_never_in_batch` |
| 1.8.2 | Protection requirements per class (encryption, integrity, retention, privacy) | met (doc) | `COMPLIANCE.md` (what is read, sent, written and kept) |
| 1.9.1 | Components communicate over encrypted channels | N/A | No component-to-component network traffic |
| 1.9.2 | Components use a TLS-verified channel | N/A | No network code: `tests/unit/test_smoke.py::test_no_network_guard_active` |
| 1.10.1 | Source control, changes tied to issues or tickets | met (doc) | Git history; the release workflow builds only from `v*` tags |
| 1.11.1 | Business-logic flows documented | met (doc) | `SKILL.md` steps; `tests/e2e/test_skill_protocol.py::test_steps_are_present_in_order_and_python_bootstrap_is_described` |
| 1.11.2 | High-value flows resist race conditions (TOCTOU) | met | `tests/unit/test_route.py::test_apply_aborts_if_target_changed_and_writes_nothing` |
| 1.11.3 | High-value flows resist attack and tampering | met | `tests/pentest/test_pt_malicious_output.py::test_a_tampered_record_cannot_name_a_file_yardmaster_does_not_write` |
| 1.12.1 | Uploaded files are stored outside the web root | N/A | No uploads, no web root |
| 1.12.2 | Uploaded files are served safely | N/A | No uploads |
| 1.14.1 | Components segregated by trust level | met | Read-only collectors are separate from writers: `tests/unit/test_safe_io.py::test_sqlite_ro_cannot_write` |
| 1.14.2 | Binary signatures, trusted endpoints, sandboxing | met | `tests/unit/test_workflows.py::test_release_gates_on_tests_and_attests_the_zip` |
| 1.14.3 | Pipeline warns of outdated or insecure components | met | `tests/unit/test_workflows.py::test_dependabot_covers_actions_and_pip` |
| 1.14.4 | Pipeline builds and verifies secure deployment | met | `tests/unit/test_build_release.py::test_checksums_file_matches` |
| 1.14.5 | Deployments sandbox risky components | N/A | No risky third-party components in the runtime (S1) |
| 1.14.6 | No unsupported client-side technologies | N/A | No client side |

## V5 Validation, sanitisation and encoding

| ID | Requirement (paraphrased) | Status | Evidence |
|---|---|---|---|
| 5.1.1 | Defend against HTTP parameter pollution | N/A | No HTTP |
| 5.1.2 | Defend against mass assignment | met | `tests/unit/test_schema.py::test_extra_keys_rejected_in_plan_and_groups` |
| 5.1.3 | Positive (allow-list) validation of all input | met | `tests/unit/test_schema.py::test_unknown_model_rejected` |
| 5.1.4 | Structured data is strongly typed and validated | met | `tests/unit/test_schema.py::test_shape_errors` |
| 5.1.5 | URL redirects go only to allow-listed targets | N/A | No redirects |
| 5.2.1 | HTML input is sanitised | N/A | No HTML is rendered |
| 5.2.2 | Unstructured data is sanitised (special characters, length) | met | `tests/unit/test_schema.py::test_verdict_field_limits` |
| 5.2.3 | Output to mail systems is sanitised | N/A | No mail |
| 5.2.4 | No `eval` or dynamic code execution | met | `tests/unit/test_stdlib_only.py::test_the_shipped_runtime_is_stdlib_only_and_clean` |
| 5.2.5 | No template injection | N/A | No template engine; writers emit from validated fields: `tests/writers/test_writers.py::test_hostile_text_cannot_change_structure` |
| 5.2.6 | No SSRF | met | No network code (S2): `tests/unit/test_smoke.py::test_no_network_guard_active` |
| 5.2.7 | Scriptable SVG content is sanitised | N/A | No SVG |
| 5.2.8 | Scriptable user content (Markdown etc.) is sandboxed or escaped | met | `tests/unit/test_emit.py::test_md_escape_neutralises_markup_and_newlines` |
| 5.3.1 | Output encoding fits the interpreter and context | met | `tests/unit/test_emit.py::test_emitted_scalars_are_single_line` |
| 5.3.2 | Output encoding preserves the chosen character set and locale | met | `tests/unit/test_safe_io.py::test_atomic_write_preserves_crlf_and_bom` |
| 5.3.3 | Context-aware escaping against reflected, stored and DOM XSS | N/A | No browser output |
| 5.3.4 | Database queries resist injection | N/A | No SQL is built from input; SQLite is opened read-only: `tests/unit/test_safe_io.py::test_sqlite_ro_cannot_write` |
| 5.3.5 | Parameterised queries or ORM | N/A | Same as 5.3.4 |
| 5.3.6 | JavaScript or JSON injection is prevented | N/A | No JavaScript is produced |
| 5.3.7 | LDAP injection is prevented | N/A | No LDAP |
| 5.3.8 | OS command injection is prevented | met | No `subprocess`, `os.system` or `shell=True` in the runtime: `tests/unit/test_stdlib_only.py::test_planted_violations_are_caught` |
| 5.3.9 | Local and remote file inclusion are prevented | met | `tests/unit/test_safe_io.py::test_contained_rejects_dotdot_and_abs` |
| 5.3.10 | XPath or XML injection is prevented | N/A | No XML or XPath |
| 5.4.1 | Memory-safe string, buffer and unsafe-memory handling | met | Managed language, and size caps before parsing: `tests/pentest/test_pt_hostile_history.py::test_a_single_51mb_line_is_skipped_without_holding_it_in_memory` |
| 5.4.2 | Format strings do not take hostile input | N/A | Python; no user-controlled format string reaches `str.format` or `%` |
| 5.4.3 | Sign, range and input validation prevent integer overflow | N/A | Python integers do not overflow; range limits are in `tests/unit/test_schema.py::test_verdict_field_limits` |
| 5.5.1 | Serialised objects have integrity checks or are encrypted | met | Run records are re-validated, and every target is re-hashed against the preview, before use (no signature on the record itself; it is owner-only 0600): `tests/unit/test_route.py::test_tampered_record_paths_outside_root_are_refused` |
| 5.5.2 | XML parsers are hardened against XXE | N/A | No XML parsing |
| 5.5.3 | Untrusted data is not deserialised unsafely | met | No `pickle`, `marshal` or `yaml.load`: `tests/unit/test_stdlib_only.py::test_planted_violations_are_caught` |
| 5.5.4 | JSON is parsed with a safe parser, never `eval` | met | `tests/pentest/test_pt_malicious_output.py::test_json_bomb_is_refused` |

## V7 Error handling and logging

| ID | Requirement (paraphrased) | Status | Evidence |
|---|---|---|---|
| 7.1.1 | Credentials and payment details are not logged | met | `tests/e2e/test_full_flow.py::test_ledger_and_export_never_leak_the_planted_secrets` |
| 7.1.2 | Other sensitive data is not logged beyond what is required | met | `tests/unit/test_batch.py::test_manifest_has_no_text`, `tests/unit/test_ledger.py::test_total_and_render_has_no_chat_text` |
| 7.1.3 | Security-relevant events are logged | partial | Rejections, applies and undos are recorded in the run record and exit codes: `tests/unit/test_route.py::test_undo_nothing_to_undo_and_double_undo`. There is no persistent audit log; accepted for a local CLI |
| 7.1.4 | Each event carries enough information to investigate | partial | The run record holds the run id, targets, hashes and timestamps: `tests/unit/test_route.py::test_apply_writes_exactly_the_previewed_text`. Same gap as 7.1.3 |
| 7.2.1 | All authentication decisions are logged | N/A | No authentication |
| 7.2.2 | All access-control decisions are logged | N/A | No users. Containment refusals exit non-zero with a safe message: `tests/unit/test_route.py::test_tampered_record_paths_outside_root_are_refused` |
| 7.3.1 | Log data is encoded against injection | met | `tests/unit/test_batch.py::test_header_fields_stay_on_one_line` |
| 7.3.3 | Logs are protected from unauthorised access and modification | met | Run records are owner-only: `tests/unit/test_route.py::test_record_file_mode_0600` |
| 7.3.4 | Time sources are synchronised | N/A | No log service; timestamps come from the host clock |
| 7.4.1 | A generic message on unexpected errors, without sensitive detail | met | `tests/pentest/test_pt_injection.py::test_cli_rejects_without_echoing_the_payload` |
| 7.4.2 | Exception handling is used throughout | met | `tests/fuzz/test_fuzz.py::test_validators_only_ever_raise_validation_error` |
| 7.4.3 | A last-resort handler catches what is left | met | `main` maps errors to exit codes and never prints a traceback with content: `tests/e2e/test_route_cli.py::test_argument_errors` |

## V8 Data protection

| ID | Requirement (paraphrased) | Status | Evidence |
|---|---|---|---|
| 8.1.1 | Sensitive data is not cached in server components | N/A | No server. The equivalent, private and short-lived temp data, is covered by `tests/pentest/test_pt_tempfiles.py::test_tempdir_is_removed_when_the_body_raises` |
| 8.1.2 | Client-side caching of sensitive data is minimised and cleared | met | `tests/e2e/test_survey.py::test_default_survey_dir_preview_and_clean` |
| 8.1.3 | Sensitive fields are not sent in a URL or query string | N/A | No HTTP |
| 8.1.4 | Abnormal request volume is detected | N/A | No requests. The nearest control, a batch-count guard, is `tests/e2e/test_survey.py::test_batch_count_guard_exit_4` |
| 8.2.1 | Anti-caching headers | N/A | No HTTP |
| 8.2.2 | No sensitive data in browser storage | N/A | No browser |
| 8.2.3 | Client-side authenticated data is cleared on logout | N/A | No sessions |
| 8.3.1 | Sensitive data goes in the body or headers, not the URL | N/A | No HTTP |
| 8.3.2 | Users can remove or export their data | met | `clean` removes survey data; `undo` removes what was written: `tests/unit/test_route.py::test_undo_restores_existing_and_removes_new`, `tests/unit/test_export_md.py::test_cli_export_md` |
| 8.3.3 | Users are told how personal data is used and consent is obtained | met (doc) | `COMPLIANCE.md`; the SKILL.md gate before analysis: `tests/e2e/test_skill_protocol.py::test_user_gate_before_analysis_and_before_apply` |
| 8.3.4 | Sensitive data is identified and has controls | met | `tests/unit/test_redact.py::test_each_rule_redacts_its_fixture` |
| 8.3.5 | Access to sensitive data is audited | N/A | Single-user local data. Nothing is read that the user's own account could not read |
| 8.3.6 | Sensitive data in memory is overwritten after use | N/A | Python cannot guarantee zeroing; lifetime is one process, which exits after the run. Accepted limit |
| 8.3.7 | Sensitive data is encrypted with approved algorithms | N/A | No sensitive data is persisted: batches live in an owner-only directory and are deleted (`tests/pentest/test_pt_tempfiles.py::test_posix_mode_is_owner_only`) |
| 8.3.8 | Personal data has a retention classification and is deleted when due | met | Batches are deleted when the run ends or on `clean`; a second survey replaces the first: `tests/e2e/test_survey.py::test_second_survey_replaces_the_first_directory` |

## V10 Malicious code

| ID | Requirement (paraphrased) | Status | Evidence |
|---|---|---|---|
| 10.2.1 | Code has no unauthorised phone-home or data collection | met | Every test runs with sockets blocked: `tests/unit/test_smoke.py::test_no_network_guard_active` |
| 10.2.2 | The app does not request unnecessary privacy-related permissions | met | No device permissions, no elevation; manifests request no hooks or tools: `tests/unit/test_manifests.py::test_manifests_declare_no_hooks_tools_permissions_or_servers` |
| 10.3.1 | Auto-update is signed and fetched securely, or absent | N/A | There is no auto-update |
| 10.3.2 | Integrity protection such as code signing for the release | met | Reproducible zip, `SHA256SUMS`, build attestation: `tests/unit/test_build_release.py::test_the_zip_is_byte_for_byte_reproducible`, `tests/unit/test_workflows.py::test_release_gates_on_tests_and_attests_the_zip` |
| 10.3.3 | Subdomain takeover is prevented | N/A | No DNS names are used |

## V12 Files and resources

| ID | Requirement (paraphrased) | Status | Evidence |
|---|---|---|---|
| 12.1.1 | Large files cannot fill storage or memory | met | `tests/pentest/test_pt_hostile_history.py::test_oversized_files_are_skipped_with_a_warning_by_every_collector` |
| 12.1.2 | Compressed files are checked against decompression bombs | N/A | No archive is ever extracted or read. The release zip is only built: `tests/unit/test_build_release.py::test_contents_are_the_skill_and_nothing_else` |
| 12.1.3 | A file-size quota per user | N/A | Single user. The per-file and per-line caps in 12.1.1 apply |
| 12.2.1 | File types are validated before use | met | Collectors open only the expected names and shapes: `tests/pentest/test_pt_hostile_history.py::test_collectors_survive_a_directory_of_garbage` |
| 12.3.1 | Filenames cannot cause path traversal | met | `tests/unit/test_safe_io.py::test_contained_rejects_dotdot_and_abs` |
| 12.3.2 | Filenames cannot cause reflected file download | N/A | No downloads |
| 12.3.3 | Untrusted files are not used for local file inclusion | met | `tests/pentest/test_pt_paths.py::test_claude_session_file_symlink_is_not_followed` |
| 12.3.4 | Untrusted files are not used for remote file inclusion | met | No network: `tests/unit/test_smoke.py::test_no_network_guard_active` |
| 12.3.5 | Untrusted files are not executed | met | No code-execution surface (S3): `tests/unit/test_stdlib_only.py::test_planted_violations_are_caught` |
| 12.3.6 | No inclusion of executable code from untrusted third parties | met | Zero runtime dependencies (S1): `tests/unit/test_stdlib_only.py::test_the_shipped_runtime_is_stdlib_only_and_clean` |
| 12.4.1 | Untrusted files are stored outside the web root | N/A | No web root |
| 12.4.2 | Untrusted files are scanned by antivirus | N/A | Files are parsed as data, never stored or served |
| 12.5.1 | Only required file types are served | N/A | Nothing is served |
| 12.5.2 | Direct requests to uploaded files cannot execute them | N/A | No uploads |
| 12.6.1 | SSRF protection with an allow-list | met | No outbound requests exist: `tests/unit/test_smoke.py::test_no_network_guard_active` |

## V14 Configuration

| ID | Requirement (paraphrased) | Status | Evidence |
|---|---|---|---|
| 14.1.1 | Build and deploy are secure and repeatable (CI/CD, automation, integrity checks) | met | `tests/unit/test_build_release.py::test_the_zip_is_byte_for_byte_reproducible` |
| 14.1.2 | Compiler flags enable protections | N/A | Interpreted code, no compiled artefact |
| 14.1.3 | Server configuration is hardened | N/A | No server |
| 14.1.4 | All components can be redeployed from a documented, tested runbook | met | The release workflow is the runbook; the zip is rebuilt byte for byte: `tests/unit/test_build_release.py::test_checksums_file_matches` |
| 14.2.1 | All components are up to date, and dependencies are checked | met | `tests/unit/test_workflows.py::test_security_workflow_runs_every_scanner`, `tests/unit/test_workflows.py::test_dependabot_covers_actions_and_pip` |
| 14.2.2 | Unneeded features, samples and documentation are removed | met | The release zip holds the skill only: `tests/unit/test_build_release.py::test_contents_are_the_skill_and_nothing_else` |
| 14.2.3 | External assets use SRI | N/A | No external assets |
| 14.2.4 | Third-party components come from trusted, maintained sources, and are pinned | met | None at runtime; build actions are pinned to SHAs: `tests/unit/test_workflows.py::test_every_action_is_pinned_to_a_full_commit_sha` |
| 14.2.5 | A software bill of materials is kept | met | CycloneDX SBOM is attached to each release: `tests/unit/test_workflows.py::test_release_gates_on_tests_and_attests_the_zip` |
| 14.2.6 | The attack surface is reduced by sandboxing or encapsulating third-party libraries | N/A | No third-party runtime libraries |
| 14.3.1 | Server and framework error messages do not disclose information | N/A | No server; for the CLI see 7.4.1 |
| 14.3.2 | Debug modes are off in production | N/A | There is no debug mode (the spec's `--debug` flag was not built); see the residual-risk note in `threat-model.md` |
| 14.3.3 | No version or component details in HTTP headers | N/A | No HTTP |
| 14.4.1 | Every response has a content type and character set | N/A | No HTTP |
| 14.4.2 | API responses carry `Content-Disposition: attachment` | N/A | No HTTP |
| 14.4.3 | A Content Security Policy is set | N/A | No HTTP |
| 14.4.4 | `X-Content-Type-Options: nosniff` | N/A | No HTTP |
| 14.4.5 | HSTS | N/A | No HTTP |
| 14.4.6 | `Referrer-Policy` | N/A | No HTTP |
| 14.4.7 | Framing is restricted | N/A | No HTTP |
| 14.5.1 | Only the HTTP methods in use are accepted | N/A | No HTTP |
| 14.5.2 | The `Origin` header is not used for authentication | N/A | No HTTP |
| 14.5.3 | CORS uses an allow-list | N/A | No HTTP |
| 14.5.4 | HTTP headers added by a trusted proxy are authenticated | N/A | No HTTP |

## Other assurance targets

| Target | State |
|---|---|
| OpenSSF Scorecard 8 or higher | Not yet measured. The workflow (`scorecard.yml`) runs on GitHub after the first push; any check below 8 will be listed here with its reason |
| SLSA Build L3 | Provenance is produced by `actions/attest-build-provenance` in `release.yml`; it is verified in `COMPLIANCE.md` |
| Branch protection, private vulnerability reporting, secret scanning | **Owner action pending.** The commands are in `docs/security/repo-hardening.md`. Record the date here once done: _not yet applied_ |
