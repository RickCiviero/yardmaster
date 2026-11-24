"""Fail if the shipped runtime imports anything outside the standard library or Yardmaster itself, uses a banned
module (network, process, native-code, deserialisation), or calls eval/exec/__import__/os.system/os.popen.

    python tools/check_stdlib_only.py [DIR]      (default: skills/yardmaster/scripts)
"""

import ast
import sys
from pathlib import Path

BANNED_MODULES = ("subprocess", "socket", "urllib.request", "urllib.error", "http", "ctypes", "pickle", "marshal", "multiprocessing",
                  "ftplib", "smtplib", "telnetlib", "xmlrpc", "imaplib", "poplib", "ssl", "asyncio.subprocess")
BANNED_CALLS = {"eval", "exec", "__import__"}
BANNED_ATTR_CALLS = {("os", "system"), ("os", "popen")}
OWN = {"yardmaster"}


def _banned(name: str) -> str | None:
    return next((b for b in BANNED_MODULES if name == b or name.startswith(b + ".")), None)


def check(root: Path) -> list[str]:
    problems: list[str] = []
    stdlib = set(sys.stdlib_module_names)
    for f in sorted(Path(root).rglob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError as e:
            problems.append(f"{f}: syntax error ({e.msg})")
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for name in names:
                top = name.split(".")[0]
                if (bad := _banned(name)) is not None:
                    problems.append(f"{f}:{node.lineno}: banned module {bad}")
                elif top not in stdlib and top not in OWN:
                    problems.append(f"{f}:{node.lineno}: {top} is not in the standard library")
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id in BANNED_CALLS:
                    problems.append(f"{f}:{node.lineno}: call to {fn.id}()")
                elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and (fn.value.id, fn.attr) in BANNED_ATTR_CALLS:
                    problems.append(f"{f}:{node.lineno}: call to {fn.value.id}.{fn.attr}()")
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else Path(__file__).resolve().parents[1] / "skills" / "yardmaster" / "scripts"
    problems = check(root)
    for p in problems:
        print(p)
    print("stdlib-only check:", "FAILED" if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
