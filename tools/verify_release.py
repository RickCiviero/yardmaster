"""Check a downloaded release file against SHA256SUMS: `python tools/verify_release.py FILE SHA256SUMS`.

Exits 0 only when FILE is listed in SHA256SUMS and its SHA-256 matches. A release user runs the same check by hand.
"""

import hashlib
import sys
from pathlib import Path


def listed_digest(sums: Path, name: str) -> str | None:
    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return parts[0].lower()
    return None


def main(argv: list[str]) -> int:
    target, sums = Path(argv[1]), Path(argv[2])
    want = listed_digest(sums, target.name)
    if want is None:
        print(f"FAIL: {target.name} is not listed in {sums.name}")
        return 1
    got = hashlib.sha256(target.read_bytes()).hexdigest()
    if got != want:
        print(f"FAIL: {target.name} has sha256 {got}, {sums.name} says {want}")
        return 1
    print(f"OK: {target.name} matches {sums.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
