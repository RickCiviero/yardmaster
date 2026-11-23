"""Anonymise a real history file into a safe test fixture.

    python tools/make_fixture.py SRC DST

Strings become `lorem-<n>` (ids become `fx-<n>`, workspace paths become `C:/ws/<n>`); keys, structure, numbers and
the few structural strings listed in KEEP survive. ALWAYS read the output before committing it.
"""

import itertools
import json
import sys
from pathlib import Path

KEEP = {"kind", "type", "role", "modelId", "model", "version", "mode", "id_kind", "initialLocation", "status"}
IDS = {"sessionId", "id", "chatId", "session_id", "uuid"}
PATHS = {"folder", "workspace", "cwd", "rootPath"}


def anonymise(obj, n, key=None, in_path_list=False):
    if isinstance(obj, dict):
        return {k: anonymise(v, n, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [anonymise(v, n, key, in_path_list or key == "k") for v in obj]
    if isinstance(obj, str):
        if key in KEEP or in_path_list:  # `k` lists hold field names: structural, keep
            return obj
        if key in IDS:
            return f"fx-{next(n)}"
        if key in PATHS:
            return f"file:///c%3A/ws/{next(n)}" if obj.startswith("file:") else f"C:/ws/{next(n)}"
        return f"lorem-{next(n)}"
    return obj


def anonymise_file(src: Path, dst: Path) -> None:
    n = itertools.count(1)
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    raw = src.read_text(encoding="utf-8", errors="replace")
    if src.suffix == ".jsonl":
        rows = []
        for line in raw.splitlines():
            try:
                rows.append(json.dumps(anonymise(json.loads(line), n)))
            except ValueError:
                continue
        dst.write_text("\n".join(rows) + "\n", encoding="utf-8")
    else:
        dst.write_text(json.dumps(anonymise(json.loads(raw), n), indent=1), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    anonymise_file(Path(sys.argv[1]), Path(sys.argv[2]))
