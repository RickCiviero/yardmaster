import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "verify_release.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _release(tmp_path: Path, content: bytes = b"zip bytes") -> tuple[Path, Path]:
    zipped = tmp_path / "yardmaster-1.0.0.zip"
    zipped.write_bytes(content)
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{hashlib.sha256(content).hexdigest()}  yardmaster-1.0.0.zip\n", encoding="utf-8")
    return zipped, sums


def test_matching_file_passes(tmp_path):
    zipped, sums = _release(tmp_path)
    result = _run(str(zipped), str(sums))
    assert result.returncode == 0, result.stdout


def test_tampered_file_fails(tmp_path):
    zipped, sums = _release(tmp_path)
    zipped.write_bytes(b"tampered")
    result = _run(str(zipped), str(sums))
    assert result.returncode == 1
    assert "sha256" in result.stdout


def test_file_missing_from_sums_fails(tmp_path):
    zipped, sums = _release(tmp_path)
    sums.write_text("0" * 64 + "  some-other.zip\n", encoding="utf-8")
    result = _run(str(zipped), str(sums))
    assert result.returncode == 1
    assert "not listed" in result.stdout


def test_star_marked_binary_entries_are_accepted(tmp_path):
    zipped, sums = _release(tmp_path)
    sums.write_text(sums.read_text(encoding="utf-8").replace("  yardmaster", " *yardmaster"), encoding="utf-8")
    assert _run(str(zipped), str(sums)).returncode == 0
