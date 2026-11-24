import json
import os
import sqlite3
import stat
import sys
from pathlib import Path

import pytest
from yardmaster.safe_io import (
    UnsafePathError,
    atomic_write,
    contained,
    iter_jsonl,
    load_json,
    private_tempdir,
    read_bytes_capped,
    read_text,
    sha256_file,
    sqlite_ro,
)


def test_contained_rejects_dotdot_and_abs(tmp_path):
    root = tmp_path / "a"
    root.mkdir()
    assert contained(root / "sub" / "f", root) == (root / "sub" / "f").resolve()
    with pytest.raises(UnsafePathError):
        contained(root / ".." / ".." / "x", root)
    with pytest.raises(UnsafePathError):
        contained(tmp_path / "elsewhere", root)
    with pytest.raises(UnsafePathError):
        contained(root.parent, root)


def test_atomic_write_refuses_symlink_target(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    link = root / "router.yml"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(UnsafePathError):
        atomic_write(link, "x", root=root, expect_sha256=sha256_file(link))
    assert outside.read_text() == "secret"


def test_atomic_write_refuses_symlinked_parent(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / ".agents").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(UnsafePathError):
        atomic_write(root / ".agents" / "r.yml", "x", root=root, expect_sha256=None)
    assert list(outside.iterdir()) == []


def test_atomic_write_hash_mismatch_aborts(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("old")
    with pytest.raises(UnsafePathError):
        atomic_write(f, "new", root=tmp_path, expect_sha256="0" * 64)
    assert f.read_text() == "old"
    with pytest.raises(UnsafePathError):  # expected missing, but it exists
        atomic_write(f, "new", root=tmp_path, expect_sha256=None)


def test_atomic_write_creates_parents_and_new_file(tmp_path):
    f = tmp_path / "a" / "b" / "f.txt"
    atomic_write(f, "hello\n", root=tmp_path, expect_sha256=None)
    assert f.read_bytes() == b"hello\n"
    assert not [p for p in f.parent.iterdir() if p.name != "f.txt"]  # no temp leftovers


def test_atomic_write_preserves_crlf_and_bom(tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"\xef\xbb\xbfx\r\ny\r\n")
    atomic_write(f, "a\nb\n", root=tmp_path, expect_sha256=sha256_file(f))
    assert f.read_bytes() == b"\xef\xbb\xbfa\r\nb\r\n"


def test_atomic_write_rejects_path_outside_root(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    with pytest.raises(UnsafePathError):
        atomic_write(tmp_path / "other.txt", "x", root=root, expect_sha256=None)


def test_iter_jsonl_partial_last_line(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_bytes(b'{"a": 1}\n\n{"b": 2}\n{"a":')
    assert list(iter_jsonl(f)) == [{"a": 1}, {"b": 2}]


def test_iter_jsonl_skips_non_dict_invalid_utf8_and_oversize(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_bytes(
        b'[1,2]\n{"t": "caf\xe9"}\n' + b'{"big": "' + b"x" * 5000 + b'"}\n{"ok": true}\n'
    )
    out = list(iter_jsonl(f, max_line=1000))
    assert out == [{"t": "caf�"}, {"ok": True}]


def test_iter_jsonl_deep_nesting(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_bytes(b"[" * 100000 + b"\n" + b'{"k": ' + b"[" * 100000 + b"\n" + b'{"ok": 1}\n')
    assert list(iter_jsonl(f)) == [{"ok": 1}]


def test_iter_jsonl_missing_file(tmp_path):
    assert list(iter_jsonl(tmp_path / "nope.jsonl")) == []


def test_load_json_bad_inputs(tmp_path):
    f = tmp_path / "a.json"
    f.write_text('{"a": 1}')
    assert load_json(f) == {"a": 1}
    f.write_text("{nope")
    assert load_json(f) is None
    f.write_bytes(b"[" * 100000)
    assert load_json(f) is None
    assert load_json(tmp_path / "missing.json") is None


def test_read_bytes_capped(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x" * 100)
    assert read_bytes_capped(f, 100) == b"x" * 100
    with pytest.raises(OSError):
        read_bytes_capped(f, 99)


def test_read_text_strips_bom_and_replaces_bad_bytes(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"\xef\xbb\xbfhi \xff")
    assert read_text(f) == "hi �"


def test_private_tempdir_mode_and_cleanup(home):
    with private_tempdir() as d:
        assert d.is_dir()
        (d / "f").write_text("x")
        if sys.platform != "win32":
            assert stat.S_IMODE(d.stat().st_mode) == 0o700
        kept = d
    assert not kept.exists()


def test_private_tempdir_cleans_up_on_exception(home):
    with pytest.raises(RuntimeError), private_tempdir() as d:
        kept = d
        raise RuntimeError("boom")
    assert not kept.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only ACL stand-in")
def test_private_tempdir_windows_refuses_outside_profile(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(elsewhere))
    monkeypatch.setenv("USERPROFILE", str(elsewhere))
    with pytest.raises(UnsafePathError), private_tempdir():
        pass


def test_sqlite_ro_cannot_write(tmp_path):
    db = tmp_path / "x.db"
    c = sqlite3.connect(db)
    c.execute("create table t(a)")
    c.execute("insert into t values (1)")
    c.commit()
    c.close()
    ro = sqlite_ro(db)
    assert ro.execute("select a from t").fetchall() == [(1,)]
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("insert into t values (2)")
    ro.close()


def test_sha256_file(tmp_path):
    f = tmp_path / "a"
    f.write_bytes(b"abc")
    assert sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert sha256_file(tmp_path / "missing") is None
    assert json.dumps(None) == "null" and os.sep  # keep imports honest
    assert isinstance(tmp_path, Path)


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions")
def test_atomic_write_refuses_junction_parent(tmp_path):
    import subprocess

    root = tmp_path / "proj"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    r = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(root / ".agents"), str(outside)], capture_output=True
    )
    assert r.returncode == 0, r.stderr
    with pytest.raises(UnsafePathError):
        atomic_write(root / ".agents" / "r.yml", "x", root=root, expect_sha256=None)
    assert list(outside.iterdir()) == []
