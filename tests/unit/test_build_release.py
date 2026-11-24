import hashlib
import zipfile
from pathlib import Path

import pytest
from build_release import build, main, write_sums
from yardmaster import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_the_zip_is_byte_for_byte_reproducible(tmp_path):
    a = build(ROOT, __version__, tmp_path / "a")
    b = build(ROOT, __version__, tmp_path / "b")
    assert a.name == f"yardmaster-{__version__}.zip" and a.read_bytes() == b.read_bytes()


def test_contents_are_the_skill_and_nothing_else(tmp_path):
    z = build(ROOT, __version__, tmp_path)
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        assert names == sorted(names)
        assert {"yardmaster/SKILL.md", "yardmaster/pricing.json", "yardmaster/LICENSE", "yardmaster/scripts/yardmaster.py",
                "yardmaster/scripts/yardmaster/cli.py"} <= set(names)
        assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc") or n.startswith(("tests", "docs", ".git", "reference"))]
        assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in zf.infolist())  # no build-time timestamps
        assert all(i.create_system == 3 and (i.external_attr >> 16) & 0o777 == 0o644 for i in zf.infolist())
        assert zf.testzip() is None


def test_checksums_file_matches(tmp_path):
    z = build(ROOT, __version__, tmp_path)
    sums = write_sums([z], tmp_path / "SHA256SUMS")
    line = sums.read_text().strip()
    assert line == f"{hashlib.sha256(z.read_bytes()).hexdigest()}  {z.name}"


def test_cli_refuses_a_version_that_is_not_the_package_version(tmp_path, capsys):
    assert main(["build_release.py", "9.9.9", str(tmp_path)]) == 1
    assert "does not match" in capsys.readouterr().out and not list(tmp_path.iterdir())
    assert main(["build_release.py", __version__, str(tmp_path)]) == 0
    assert (tmp_path / f"yardmaster-{__version__}.zip").is_file() and (tmp_path / "SHA256SUMS").is_file()


@pytest.mark.parametrize("bad", ["../1.0.0", "1.0", "v1.0.0", "1.0.0; rm", ""])
def test_malformed_versions_are_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        build(ROOT, bad, tmp_path)
