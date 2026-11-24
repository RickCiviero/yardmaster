"""Build the reproducible release zip and its checksums.

    python tools/build_release.py VERSION OUT_DIR

The zip holds the skill folder (as `yardmaster/`) and the licence: sorted entries, fixed timestamps and permissions, no
caches, so the same source always gives the same bytes and a reviewer can rebuild and compare.
"""

import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPOCH = (1980, 1, 1, 0, 0, 0)
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def build(root: Path, version: str, out_dir: Path) -> Path:
    if not VERSION.match(version):
        raise ValueError(f"bad version {version!r}; expected MAJOR.MINOR.PATCH")
    skill = Path(root) / "skills" / "yardmaster"
    files = {f"yardmaster/{p.relative_to(skill).as_posix()}": p for p in skill.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    files["yardmaster/LICENSE"] = Path(root) / "LICENSE"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"yardmaster-{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            data = files[name].read_bytes().replace(b"\r\n", b"\n") if files[name].suffix in {".py", ".md", ".json"} else files[name].read_bytes()
            z.writestr(info, data)
    return out


def write_sums(files: list[Path], out: Path) -> Path:
    out.write_text("".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n" for f in files), encoding="utf-8", newline="\n")
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    sys.path.insert(0, str(ROOT / "skills" / "yardmaster" / "scripts"))
    from yardmaster import __version__

    if argv[1] != __version__:
        print(f"tag version {argv[1]} does not match the package version {__version__}")
        return 1
    out_dir = Path(argv[2])
    z = build(ROOT, argv[1], out_dir)
    write_sums([z], out_dir / "SHA256SUMS")
    print(f"Built {z} and SHA256SUMS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
