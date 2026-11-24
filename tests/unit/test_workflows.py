"""Supply-chain controls as tests: every workflow is checked, so a regression cannot slip in unnoticed."""

import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
HIGH = {"id-token", "attestations", "security-events", "contents"}


def _load(p):
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    doc["on"] = doc.pop(True, doc.get("on"))  # YAML reads a bare `on:` as the boolean True
    return doc


def _steps(doc):
    for job in doc["jobs"].values():
        yield from job.get("steps", [])


def test_the_expected_workflows_exist():
    assert {p.name for p in WORKFLOWS} >= {"ci.yml", "security.yml", "scorecard.yml", "release.yml", "fuzz.yml"}


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_full_commit_sha(wf):
    for step in _steps(_load(wf)):
        if "uses" in step and not step["uses"].startswith("./"):
            assert PINNED.match(step["uses"]), f"{wf.name}: {step['uses']} is not pinned to a 40-hex commit"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_permissions_are_least_privilege(wf):
    doc = _load(wf)
    assert "permissions" in doc, f"{wf.name} must declare top-level permissions"
    top = doc["permissions"]
    assert top != "write-all" and (top in ({}, None) or all(v in ("read", "none") for v in top.values())), "top-level must be read-only"
    for name, job in doc["jobs"].items():
        for scope, level in (job.get("permissions") or {}).items():
            assert level in ("read", "write", "none") and (level == "read" or scope in HIGH | {"contents", "pull-requests"}), (name, scope)
        assert "timeout-minutes" in job, f"{wf.name}:{name} needs a timeout"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_checkout_never_persists_credentials(wf):
    for step in _steps(_load(wf)):
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step.get("with", {}).get("persist-credentials") is False, wf.name


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_no_script_injection_or_pipe_to_shell(wf):
    doc = _load(wf)
    assert "pull_request_target" not in (doc["on"] if isinstance(doc["on"], dict) else {})
    for step in _steps(doc):
        run = step.get("run", "")
        assert "${{ secrets." not in run and "${{ github.event" not in run and "${{ github.head_ref" not in run, step
        assert not re.search(r"curl[^\n|]*\|\s*(ba)?sh|wget[^\n|]*\|\s*(ba)?sh", run), step


def test_release_only_runs_on_version_tags_and_is_the_only_one_that_signs():
    rel = _load(ROOT / ".github" / "workflows" / "release.yml")
    assert rel["on"] == {"push": {"tags": ["v*"]}}
    perms = rel["jobs"]["release"]["permissions"]
    assert perms["id-token"] == "write" and perms["attestations"] == "write" and perms["contents"] == "write"
    for wf in WORKFLOWS:
        if wf.name not in ("release.yml", "scorecard.yml"):
            for job in _load(wf)["jobs"].values():
                assert "id-token" not in (job.get("permissions") or {}), wf.name


def test_release_gates_on_tests_and_attests_the_zip():
    steps = _load(ROOT / ".github" / "workflows" / "release.yml")["jobs"]["release"]["steps"]
    text = yaml.dump(steps)
    assert "pytest" in text and "build_release.py" in text and "attest-build-provenance" in text and "sbom" in text and "SHA256SUMS" in text


def test_security_workflow_runs_every_scanner():
    text = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    for needle in ("codeql-action/init", "semgrep", ".semgrep/yardmaster.yml", "bandit", "gitleaks", "pip-audit", "check_stdlib_only",
                   "pytest -m pentest", "windows-latest", "macos-latest", "ubuntu-latest", "security-extended"):
        assert needle in text, needle


def test_fuzz_workflow_is_nightly_with_a_heavy_example_count():
    doc = _load(ROOT / ".github" / "workflows" / "fuzz.yml")
    assert "schedule" in doc["on"] and "20000" in (ROOT / ".github" / "workflows" / "fuzz.yml").read_text(encoding="utf-8")


def test_dependabot_covers_actions_and_pip():
    doc = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    assert {u["package-ecosystem"] for u in doc["updates"]} == {"github-actions", "pip"} and doc["version"] == 2


def test_semgrep_rules_are_well_formed_and_cover_the_bans():
    doc = yaml.safe_load((ROOT / ".semgrep" / "yardmaster.yml").read_text(encoding="utf-8"))
    ids = [r["id"] for r in doc["rules"]]
    assert len(ids) == len(set(ids))
    for r in doc["rules"]:
        assert {"id", "languages", "severity", "message"} <= set(r) and r["severity"] == "ERROR"
        assert any(k in r for k in ("pattern", "patterns", "pattern-either", "pattern-regex"))
    blob = (ROOT / ".semgrep" / "yardmaster.yml").read_text(encoding="utf-8")
    for needle in ("eval", "exec", "os.system", "shell=True", "pickle", "yaml.load", "socket", "subprocess", "print("):
        assert needle in blob, needle


def test_gitleaks_config_extends_the_defaults():
    cfg = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
    assert cfg["extend"]["useDefault"] is True
