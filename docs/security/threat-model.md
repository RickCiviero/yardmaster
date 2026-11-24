# Threat model (STRIDE)

Yardmaster is a local CLI plus a skill file. It reads the chat history your AI harnesses already keep on disk, redacts it,
hands redacted batches to **the AI provider your harness already uses**, validates what comes back, and writes small,
marked blocks into routing config files after you approve a diff. It has no server, no account, no network code and no
third-party runtime dependency.

Every row below names the control (S-numbers are defined in the design spec, section 9.2) and **the test that proves it**,
written `file::test`. `tests/unit/test_docs_links.py` fails the build if a cited test does not exist.

## Assets

| Asset | Why it matters |
|---|---|
| Chat content | It can hold code, customer data and secrets. |
| Secrets inside chats | API keys and tokens that were pasted into a chat at some point. |
| The user's config files | `CLAUDE.md`, `AGENTS.md`, `.github/agents/*`, Codex `config.toml` and similar. A bad write changes how the user's agents behave. |
| Integrity of routing decisions | A forged verdict could route sensitive work to a weaker or unapproved model. |

## Adversaries

| | Adversary | Capability |
|---|---|---|
| (a) | **Malicious text inside old chats** | Prompt injection: the chat history is attacker-influenced data (a web page, an issue, a pasted file). |
| (b) | **Malicious or corrupt history files** | Parser attacks: huge lines, deep nesting, bad encodings, symlinks, hostile SQLite. |
| (c) | **Other local users or processes** | Read our temp files, race a write, swap a target for a symlink. |
| (d) | **Supply chain** | A tampered release, dependency, workflow action or pricing file. |
| (e) | **A confused or compromised model output** | The model returns paths, markup, other people's model ids or oversized JSON. |

## STRIDE tables

S = Spoofing, T = Tampering, R = Repudiation, I = Information disclosure, D = Denial of service, E = Elevation of privilege.

### (a) Malicious text inside old chats

| Cat | Threat | Control | Test that proves it |
|---|---|---|---|
| T | Chat text forges the data fence or a chat header so later text is read as instructions. | S6 | `tests/pentest/test_pt_injection.py::test_chat_text_cannot_break_the_fence_or_forge_headers` |
| T | Forged chat header inside a body. | S6 | `tests/unit/test_batch.py::test_forged_chat_header_in_body_is_neutralised` |
| T | A fence breakout in a tool result. | S6 | `tests/unit/test_batch.py::test_fence_breakout_neutralised` |
| T | The fence is guessable, so an attacker pre-writes the closing line. | S6 | `tests/unit/test_batch.py::test_nonce_differs_per_batch` |
| E | The model is talked into putting a path, URL or command into a verdict field. | S6 | `tests/pentest/test_pt_injection.py::test_every_hostile_payload_is_rejected_in_every_free_text_field` |
| E | Injected text changes the structure of a written file or touches another file. | S6, S7 | `tests/pentest/test_pt_injection.py::test_passing_text_never_changes_structure_or_touches_other_files` |
| T | A verdict is forged for a chat that was never surveyed. | S6 | `tests/pentest/test_pt_injection.py::test_a_verdict_cannot_be_forged_for_a_chat_that_was_not_surveyed` |
| I | The error message repeats the payload back into a log or terminal. | S11 | `tests/pentest/test_pt_injection.py::test_cli_rejects_without_echoing_the_payload` |
| T | Hostile text breaks YAML or TOML structure in a writer. | S6, S7 | `tests/writers/test_writers.py::test_hostile_text_cannot_change_structure` |
| T | Hostile text breaks out of a Markdown block. | S6 | `tests/unit/test_emit.py::test_md_escape_neutralises_markup_and_newlines` |
| I | A secret pasted into a chat reaches a batch, so the provider sees it. | S5 | `tests/unit/test_batch.py::test_redaction_counts_reported_and_secret_never_in_batch` |
| I | A secret straddles the per-tool-output cap and survives truncation. | S5 | `tests/unit/test_batch.py::test_secret_straddling_tool_cap_is_redacted_before_truncation` |
| I | A secret reaches a ledger or an export. | S5, S8 | `tests/e2e/test_full_flow.py::test_ledger_and_export_never_leak_the_planted_secrets` |
| I | A secret reaches a file written for any harness. | S5 | `tests/e2e/test_full_flow.py::test_full_flow_each_target` |

### (b) Malicious or corrupt history files

| Cat | Threat | Control | Test that proves it |
|---|---|---|---|
| E | A symlinked project directory sends a collector outside its root (Claude Code). | S4 | `tests/pentest/test_pt_paths.py::test_claude_project_dir_link_is_not_followed` |
| E | A symlinked subagents directory (Claude Code). | S4 | `tests/pentest/test_pt_paths.py::test_claude_subagents_dir_link_is_not_followed` |
| E | A symlinked session file (Claude Code). | S4 | `tests/pentest/test_pt_paths.py::test_claude_session_file_symlink_is_not_followed` |
| E | A symlinked chat-sessions directory (VS Code Copilot). | S4 | `tests/pentest/test_pt_paths.py::test_vscode_chat_sessions_dir_link_is_not_followed` |
| E | A symlinked session directory (Copilot CLI). | S4 | `tests/pentest/test_pt_paths.py::test_copilot_cli_session_dir_link_is_not_followed` |
| E | A symlinked day directory (Codex). | S4 | `tests/pentest/test_pt_paths.py::test_codex_day_dir_link_is_not_followed` |
| E | A `..` or absolute path escapes the containment check. | S4, S7 | `tests/unit/test_safe_io.py::test_contained_rejects_dotdot_and_abs` |
| E | A Windows junction used as a parent directory. | S4, S7 | `tests/unit/test_safe_io.py::test_atomic_write_refuses_junction_parent` |
| D | A file larger than the per-file cap exhausts memory. | S4 | `tests/pentest/test_pt_hostile_history.py::test_oversized_files_are_skipped_with_a_warning_by_every_collector` |
| D | One 51 MB line is read into memory. | S4 | `tests/pentest/test_pt_hostile_history.py::test_a_single_51mb_line_is_skipped_without_holding_it_in_memory` |
| D | Deeply nested JSON triggers a recursion error. | S4 | `tests/pentest/test_pt_hostile_history.py::test_deeply_nested_json_lines_are_skipped_not_fatal` |
| D | Invalid UTF-8, NUL bytes or lone surrogates crash the pipeline. | S4, S5 | `tests/pentest/test_pt_hostile_history.py::test_invalid_utf8_nul_and_lone_surrogates_survive_the_whole_pipeline` |
| D | A change-log with absurd indices makes a replay run away. | S4 | `tests/pentest/test_pt_hostile_history.py::test_absurd_change_log_operations_do_not_crash_or_run_away` |
| T | A SQLite file with triggers, views or an extension tries to write. | S4 | `tests/pentest/test_pt_hostile_history.py::test_sqlite_trigger_view_and_extension_attempts_cannot_write` |
| D | A directory of garbage files. | S4 | `tests/pentest/test_pt_hostile_history.py::test_collectors_survive_a_directory_of_garbage` |
| D | Byte-level corruption of any collector input. | S4 | `tests/fuzz/test_fuzz.py::test_collectors_survive_byte_level_corruption` |
| D | A regex in the redactor backtracks catastrophically on hostile text. | S5 | `tests/pentest/test_pt_redos.py::test_every_rule_is_fast_on_every_adversarial_input` |
| D | The whole redactor is slow on a long adversarial line. | S5 | `tests/pentest/test_pt_redos.py::test_the_whole_redactor_stays_bounded` |
| I | Output is not encodable, so a write fails halfway. | S5 | `tests/pentest/test_pt_hostile_history.py::test_redact_output_is_always_encodable` |

### (c) Other local users or processes

| Cat | Threat | Control | Test that proves it |
|---|---|---|---|
| I | Another user reads the batches in a world-readable temp directory. | S8 | `tests/pentest/test_pt_tempfiles.py::test_posix_mode_is_owner_only` |
| I | On Windows, the batches land outside the user profile. | S8 | `tests/pentest/test_pt_tempfiles.py::test_windows_dir_is_inside_the_user_profile` |
| E | A predictable temp name lets another process pre-create it. | S8 | `tests/pentest/test_pt_tempfiles.py::test_names_are_unpredictable` |
| I | Batches linger after Ctrl-C. | S8 | `tests/pentest/test_pt_tempfiles.py::test_tempdir_is_removed_even_when_interrupted_by_sigint` |
| I | Batches linger after an exception. | S8 | `tests/pentest/test_pt_tempfiles.py::test_tempdir_is_removed_when_the_body_raises` |
| I | The run record (which holds the diff) is readable by others. | S8 | `tests/unit/test_route.py::test_record_file_mode_0600` |
| T | The target is swapped for a symlink between diff and apply (TOCTOU). | S7 | `tests/unit/test_safe_io.py::test_atomic_write_refuses_symlink_target` |
| T | The target's parent becomes a link between diff and apply. | S7 | `tests/unit/test_route.py::test_apply_aborts_if_parent_became_a_link` |
| T | The target file is edited between diff and apply. | S7 | `tests/unit/test_route.py::test_apply_aborts_if_target_changed_and_writes_nothing` |
| T | A new file appears where the diff expected none. | S7 | `tests/unit/test_route.py::test_apply_aborts_if_new_target_appeared` |
| T | The hash check on write is bypassed. | S7 | `tests/unit/test_safe_io.py::test_atomic_write_hash_mismatch_aborts` |
| T | A crash halfway through leaves half the files written. | S7 | `tests/unit/test_route.py::test_apply_rolls_back_on_midway_failure` |
| T | A run is applied twice. | S7 | `tests/unit/test_route.py::test_apply_twice_is_refused` |
| E | Something other than the user approves the write. | S7 | `tests/unit/test_route.py::test_wrong_code_always_aborts_even_without_tty` |
| T | The user edits a file after we wrote it and `undo` clobbers the edit. | S7 | `tests/unit/test_route.py::test_undo_refuses_if_user_edited_after` |
| R | The user cannot get back to the previous state. | S7 | `tests/unit/test_route.py::test_undo_restores_existing_and_removes_new` |
| T | A writer edits text outside its marked block. | S7 | `tests/writers/test_writers.py::test_claude_md_outside_block_untouched` |
| E | A writer reaches outside the project root or the harness config directory. | S7 | `tests/writers/test_writers.py::test_writers_stay_inside_their_roots` |
| T | CRLF files or a BOM are rewritten by an edit. | S7 | `tests/unit/test_safe_io.py::test_atomic_write_preserves_crlf_and_bom` |

### (d) Supply chain

| Cat | Threat | Control | Test that proves it |
|---|---|---|---|
| T | A third-party runtime dependency is added. | S1 | `tests/unit/test_stdlib_only.py::test_the_shipped_runtime_is_stdlib_only_and_clean` |
| T | A banned call (`subprocess`, `eval`, `pickle`, sockets) is slipped in. | S1, S2, S3 | `tests/unit/test_stdlib_only.py::test_planted_violations_are_caught` |
| I | Any code path opens a network connection. | S2 | `tests/unit/test_smoke.py::test_no_network_guard_active` (the `no_network` fixture in `tests/conftest.py` is autouse for the whole suite) |
| T | A GitHub Action is repointed at malicious code (mutable tag). | S10 | `tests/unit/test_workflows.py::test_every_action_is_pinned_to_a_full_commit_sha` |
| E | A workflow has more token permission than it needs. | S10 | `tests/unit/test_workflows.py::test_permissions_are_least_privilege` |
| I | The checkout leaves a credential on disk for later steps. | S10 | `tests/unit/test_workflows.py::test_checkout_never_persists_credentials` |
| E | Script injection through event data or pipe-to-shell in a workflow. | S10 | `tests/unit/test_workflows.py::test_no_script_injection_or_pipe_to_shell` |
| T | A release is cut from something other than a version tag, or signed by another workflow. | S10 | `tests/unit/test_workflows.py::test_release_only_runs_on_version_tags_and_is_the_only_one_that_signs` |
| T | A release ships from a red tree or without provenance. | S10 | `tests/unit/test_workflows.py::test_release_gates_on_tests_and_attests_the_zip` |
| T | The scanners (CodeQL, Semgrep, Bandit, gitleaks, pip-audit) stop running. | S10 | `tests/unit/test_workflows.py::test_security_workflow_runs_every_scanner` |
| T | Dependabot stops covering Actions and dev dependencies. | S10 | `tests/unit/test_workflows.py::test_dependabot_covers_actions_and_pip` |
| T | The Semgrep ban rules are removed or malformed. | S3, S10 | `tests/unit/test_workflows.py::test_semgrep_rules_are_well_formed_and_cover_the_bans` |
| T | Two builds of the same tag differ, so a checksum proves nothing. | S10 | `tests/unit/test_build_release.py::test_the_zip_is_byte_for_byte_reproducible` |
| T | The zip contains something other than the skill. | S10 | `tests/unit/test_build_release.py::test_contents_are_the_skill_and_nothing_else` |
| T | `SHA256SUMS` does not match the zip. | S10 | `tests/unit/test_build_release.py::test_checksums_file_matches` |
| T | A release is built with a version that is not the package version. | S10 | `tests/unit/test_build_release.py::test_cli_refuses_a_version_that_is_not_the_package_version` |
| T | A manifest requests hooks, extra permissions or auto-approval. | S10 | `tests/unit/test_manifests.py::test_manifests_declare_no_hooks_tools_permissions_or_servers` |

### (e) A confused or compromised model output

| Cat | Threat | Control | Test that proves it |
|---|---|---|---|
| D | Oversized model output is parsed into memory. | S6 | `tests/pentest/test_pt_malicious_output.py::test_oversized_model_output_is_refused_before_it_is_parsed` |
| D | A JSON bomb. | S6 | `tests/pentest/test_pt_malicious_output.py::test_json_bomb_is_refused` |
| D | A thousand groups in one plan. | S6 | `tests/pentest/test_pt_malicious_output.py::test_a_thousand_groups_are_rejected` |
| E | A plan with path fields, YAML/TOML payloads or marker-closing Markdown. | S6, S7 | `tests/pentest/test_pt_malicious_output.py::test_malicious_plans_are_rejected` |
| E | A tampered run record names a file Yardmaster does not write. | S7 | `tests/pentest/test_pt_malicious_output.py::test_a_tampered_record_cannot_name_a_file_yardmaster_does_not_write` |
| E | A tampered record names a path outside the root. | S7 | `tests/unit/test_route.py::test_tampered_record_paths_outside_root_are_refused` |
| D | A tampered record with a huge payload. | S7 | `tests/pentest/test_pt_malicious_output.py::test_a_tampered_record_with_a_huge_payload_is_refused` |
| E | A model the admin denied is smuggled back through `prefer`. | S6, S9 | `tests/pentest/test_pt_malicious_output.py::test_policy_denied_models_cannot_be_smuggled_back_in_through_prefer` |
| S | A model id that does not belong to the chat's own harness (spoofing). | S6 | `tests/unit/test_schema.py::test_model_is_checked_against_the_chats_own_harness` |
| S | An unknown model id. | S6 | `tests/unit/test_schema.py::test_unknown_model_rejected` |
| E | Extra keys smuggled into the plan or a group. | S6 | `tests/unit/test_schema.py::test_extra_keys_rejected_in_plan_and_groups` |
| T | Free text (injection) in a verdict. | S6 | `tests/unit/test_schema.py::test_free_text_injection_rejected_in_verdicts` |
| T | Free text (injection) in a plan. | S6 | `tests/unit/test_schema.py::test_free_text_injection_rejected_in_plan` |
| T | Valid-looking text still changes a written file's structure. | S6, S7 | `tests/fuzz/test_fuzz.py::test_any_text_that_passes_validation_cannot_change_a_written_files_structure` |
| D | The validators raise something other than a clean `ValidationError`. | S6, S11 | `tests/fuzz/test_fuzz.py::test_validators_only_ever_raise_validation_error` |

## Cross-cutting

| Cat | Threat | Control | Test that proves it |
|---|---|---|---|
| I | More chat data is sent than the user meant to share. | S9 | `tests/e2e/test_survey.py::test_cost_gate_exit_3` |
| I | A huge run is started without the user noticing. | S9 | `tests/e2e/test_survey.py::test_batch_count_guard_exit_4` |
| I | The user cannot narrow what is sent to one project or exclude a workspace. | S9 | `tests/e2e/test_survey.py::test_exclude_workspace` |
| I | A user config widens what the admin policy narrowed. | S9 | `tests/unit/test_settings.py::test_policy_user_cannot_widen` |
| I | The admin policy is silently ignored on a bad value. | S9 | `tests/unit/test_settings.py::test_invalid_values_fail_closed` |
| I | A manifest or report carries chat text. | S8, S11 | `tests/unit/test_batch.py::test_manifest_has_no_text` |
| I | The ledger shows chat text. | S11 | `tests/unit/test_ledger.py::test_total_and_render_has_no_chat_text` |
| I | An unreadable input is echoed back with its content. | S11 | `tests/e2e/test_validate_cli.py::test_validate_unreadable_inputs` |
| E | The skill protocol lets `--apply` run before the user approves. | S7 | `tests/e2e/test_skill_protocol.py::test_apply_appears_only_in_the_apply_step` |
| E | The skill skips the user gate before analysis or apply. | S7, S9 | `tests/e2e/test_skill_protocol.py::test_user_gate_before_analysis_and_before_apply` |
| R | A reviewer cannot find how to report a vulnerability or verify a release. | S12 | `tests/unit/test_docs_links.py::test_the_docs_the_plan_promises_exist` |

## Residual risk and what is not covered

- **The provider.** Redacted batches go to the model provider you already trust through your harness. Protection against that provider is out of scope (design spec 9.5).
- **A compromised local account.** An attacker who already runs as you can read the history directly. Out of scope (9.5).
- **Redaction is best effort.** The rules port the gitleaks defaults plus an entropy detector. A secret in a format nobody has written a rule for, and short enough to look ordinary, can pass. This is why the batches can be inspected with `preview` before anything is sent.
- **Not run on this machine.** CodeQL, Semgrep, Bandit, gitleaks, pip-audit and OpenSSF Scorecard run only on GitHub. See `docs/security/repo-hardening.md` for the one-time repository settings the owner still has to apply.
- **No `--debug` flag exists.** The design spec (S11) says `--debug` still redacts. The CLI has no such flag, so there is no debug output to leak; if one is added, it needs a test first.
