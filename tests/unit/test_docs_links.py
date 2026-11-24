"""Every `file::test` the security docs cite must be a real test, so the claims cannot rot silently."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = [ROOT / "docs" / "security" / "threat-model.md", ROOT / "docs" / "security" / "asvs-l2.md"]
REF = re.compile(r"(tests/[\w/]+\.py)::(test_\w+)")


@pytest.fixture(scope="module")
def collected() -> set[tuple[str, str]]:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    # node ids look like tests/unit/test_x.py::test_y or ...::test_y[param]
    return {(m[1], m[2]) for m in REF.finditer(out.replace("\\", "/"))}


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_every_cited_test_exists(doc, collected):
    refs = REF.findall(doc.read_text(encoding="utf-8"))
    assert refs, f"{doc.name} cites no tests"
    missing = sorted({f"{f}::{t}" for f, t in refs if (f, t) not in collected})
    assert not missing, missing


def test_every_control_is_cited_by_the_threat_model():
    text = DOCS[0].read_text(encoding="utf-8")
    assert [n for n in range(1, 13) if not re.search(rf"\bS{n}\b", text)] == []


def test_the_docs_the_plan_promises_exist():
    for name in ("SECURITY.md", "COMPLIANCE.md", "docs/security/data-flow.md"):
        assert (ROOT / name).is_file(), name
