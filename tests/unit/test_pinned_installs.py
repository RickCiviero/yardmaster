"""Every pip install in a workflow is hash-locked, and every lock file pins each package to hashes."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
LOCKS = sorted((ROOT / ".github" / "requirements").glob("*.txt"))
PIP_INSTALL = re.compile(r"\bpip\S*\s+install\b")
# The SBOM step installs the project itself, and its build backend is not hash-locked. Open item in docs/security/asvs-l2.md.
KNOWN_UNLOCKED = {"sbom-env/bin/pip install ."}


def _run_lines():
    for wf in WORKFLOWS:
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        for job in doc["jobs"].values():
            for step in job.get("steps", []):
                for line in step.get("run", "").splitlines():
                    yield wf.name, line.strip()


def test_every_pip_install_in_a_workflow_is_hash_locked_except_the_known_sbom_build():
    for name, line in _run_lines():
        if PIP_INSTALL.search(line) and "--require-hashes" not in line:
            assert line in KNOWN_UNLOCKED, f"{name}: {line}"


def test_every_lock_file_pins_each_package_to_hashes():
    assert LOCKS, "no lock files found"
    for lock in LOCKS:
        blocks = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", lock.read_text(encoding="utf-8"))
        pinned = [b for b in blocks if re.match(r"[A-Za-z0-9_.\-]+==", b)]
        assert pinned, lock.name
        for block in pinned:
            assert "--hash=sha256:" in block, f"{lock.name}: {block.splitlines()[0]}"
