"""The install check tests every documented channel with tools pinned to exact versions and integrity hashes."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".github" / "install-check"
WORKFLOW = ROOT / ".github" / "workflows" / "install-check.yml"
EXACT = re.compile(r"^\d+\.\d+\.\d+$")


def _manifest() -> dict:
    return json.loads((TOOLS / "package.json").read_text(encoding="utf-8"))["dependencies"]


def test_every_tool_is_pinned_to_an_exact_version():
    deps = _manifest()
    assert deps and all(EXACT.match(v) for v in deps.values()), deps


def test_lock_file_matches_the_manifest_and_hashes_every_package():
    lock = json.loads((TOOLS / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"][""]["dependencies"] == _manifest()
    for path, entry in lock["packages"].items():
        if path and not entry.get("link"):
            assert entry.get("integrity", "").startswith("sha512-"), path


def test_workflow_covers_every_documented_channel():
    text = WORKFLOW.read_text(encoding="utf-8")
    for needle in (
        "plugin marketplace add",
        "plugin install yardmaster@yardmaster",
        "-a codex",
        "-a github-copilot",
        "extensions install",
        "verify_release.py",
        "gh attestation verify",
        "check.sh",
    ):
        assert needle in text, needle


def test_workflow_never_fetches_an_unpinned_tool():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "@latest" not in text
    assert "npm install" not in text
    assert "npm ci" in text


def test_workflow_runs_on_all_three_systems():
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["channels"]
    assert job["strategy"]["matrix"]["os"] == ["ubuntu-latest", "windows-latest", "macos-latest"]
