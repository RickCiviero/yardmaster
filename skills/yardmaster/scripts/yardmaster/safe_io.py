"""Every filesystem touch in Yardmaster goes through here: capped, contained, symlink-aware."""

import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MAX_FILE = 200_000_000
MAX_LINE = 50_000_000
_BOM = b"\xef\xbb\xbf"
_REPARSE_POINT = 0x400  # Windows symlink/junction attribute


class UnsafePathError(Exception):
    pass


def contained(path: Path, root: Path) -> Path:
    """Resolve `path` and require it to live inside `root`."""
    p, r = Path(path).resolve(), Path(root).resolve()
    try:
        p.relative_to(r)
    except ValueError:
        raise UnsafePathError(f"{p} is outside {r}") from None
    if p == r:
        raise UnsafePathError(f"{p} is the root itself")
    return p


def _is_link(p: Path) -> bool:
    if p.is_symlink():
        return True
    try:
        attrs = getattr(os.lstat(p), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & _REPARSE_POINT)


def has_link_below(path: Path, root: Path) -> bool:
    """True if any component of `path` BELOW `root` is a symlink or junction (root itself may be one a user made)."""
    abs_p, abs_root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    try:
        rel = abs_p.relative_to(abs_root)
    except ValueError:
        return True
    cur = abs_root
    for part in rel.parts:
        cur = cur / part
        if (cur.exists() or cur.is_symlink()) and _is_link(cur):
            return True
    return False


def _open_fd(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    return os.open(path, flags)


def read_bytes_capped(path: Path, max_bytes: int = MAX_FILE) -> bytes:
    fd = _open_fd(Path(path))
    with os.fdopen(fd, "rb") as f:
        if os.fstat(f.fileno()).st_size > max_bytes:
            raise OSError(f"{path} is larger than {max_bytes} bytes")
        return f.read(max_bytes + 1)


def read_text(path: Path, max_bytes: int = MAX_FILE) -> str:
    return read_bytes_capped(path, max_bytes).decode("utf-8-sig", errors="replace")


def iter_jsonl(path: Path, max_line: int = MAX_LINE) -> Iterator[dict]:
    """Yield the dict lines of a JSONL file; skip anything blank, malformed, oversized or too deep."""
    try:
        with os.fdopen(_open_fd(Path(path)), "rb") as f:  # O_NOFOLLOW where available: a symlinked file is refused
            while True:
                raw = f.readline(max_line + 1)
                if not raw:
                    return
                if len(raw) > max_line and not raw.endswith(b"\n"):
                    while True:  # discard the rest of the oversized line without holding it
                        chunk = f.readline(1 << 20)
                        if not chunk or chunk.endswith(b"\n"):
                            break
                    continue
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line.decode("utf-8", errors="replace"))
                except (ValueError, RecursionError):
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


MAX_JSON = 8_000_000  # model output (verdicts, plan) and manifests: far above any real size, far below a memory bomb


def load_json(path: Path, max_bytes: int = MAX_FILE) -> object | None:
    try:
        return json.loads(read_text(path, max_bytes))
    except (OSError, ValueError, RecursionError):
        return None


def sqlite_ro(path: Path) -> sqlite3.Connection:
    """Open a SQLite file strictly read-only and immutable (never locks or modifies the app's DB)."""
    uri = Path(path).resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA trusted_schema=OFF")
    with contextlib.suppress(AttributeError, sqlite3.NotSupportedError):
        conn.enable_load_extension(False)
    return conn


def _under(p: Path, base: str | None) -> bool:
    if not base:
        return False
    try:
        Path(os.path.normcase(p.resolve())).relative_to(os.path.normcase(Path(base).resolve()))
        return True
    except ValueError:
        return False


def make_private_dir() -> Path:
    """A fresh owner-only temp dir. The CALLER owns cleanup."""
    d = Path(tempfile.mkdtemp(prefix="ym-"))
    try:
        if sys.platform == "win32":
            # shortcut: no ctypes ACL edit; rely on the per-user temp dir and refuse anything else
            if not any(_under(d, os.environ.get(k)) for k in ("LOCALAPPDATA", "USERPROFILE")):
                raise UnsafePathError(f"temp dir {d} is outside the user profile")
        else:
            os.chmod(d, 0o700)
    except BaseException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return d


@contextmanager
def private_tempdir() -> Iterator[Path]:
    d = make_private_dir()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def check_target(path: Path, root: Path, expect_sha256: str | None) -> Path:
    """Raise unless `path` is inside `root`, has no link on the way, and still has the approved hash."""
    abs_p, abs_root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    try:
        rel = abs_p.relative_to(abs_root)
    except ValueError:
        raise UnsafePathError(f"{abs_p} is outside {abs_root}") from None
    cur = abs_root
    for part in rel.parts:  # no symlink or junction anywhere below the root
        cur = cur / part
        if (cur.exists() or cur.is_symlink()) and _is_link(cur):
            raise UnsafePathError(f"{cur} is a link")
    target = contained(abs_p, abs_root)
    if sha256_file(target) != expect_sha256:
        raise UnsafePathError(f"{target} changed since it was previewed")
    return target


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Raw atomic replace (no EOL/BOM handling): used to restore a backup byte-for-byte."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".ym-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def atomic_write(path: Path, text: str, *, root: Path, expect_sha256: str | None) -> None:
    """Replace `path` with `text` only if it still has the hash the user approved. Never follows links."""
    target = check_target(path, root, expect_sha256)

    bom, crlf = False, False
    if target.exists():
        old = target.read_bytes()
        bom, crlf = old.startswith(_BOM), b"\r\n" in old
    body = text.replace("\r\n", "\n")
    if crlf:
        body = body.replace("\n", "\r\n")
    data = (_BOM if bom else b"") + body.encode("utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".ym-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
