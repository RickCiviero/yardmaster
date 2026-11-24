"""Edit only a marked block inside a shared file (CLAUDE.md, AGENTS.md, config.toml); never touch the rest.

A block may carry a TAG (e.g. the harness) so several tools can keep independent blocks in one shared file:
`<!-- yardmaster:begin codex v1 -->` ... `<!-- yardmaster:end codex -->`. Untagged markers are the default.
"""

from typing import Literal


class BlockError(Exception):
    pass


def markers(style: str, tag: str = "") -> tuple[str, str]:
    if style not in ("md", "hash"):
        raise ValueError(f"unknown block style {style!r}")
    sp = f" {tag}" if tag else ""
    if style == "md":
        return f"<!-- yardmaster:begin{sp} v1 -->", f"<!-- yardmaster:end{sp} -->"
    return f"# yardmaster:begin{sp} v1", f"# yardmaster:end{sp}"


def replace_block(text: str, body: str, *, style: Literal["md", "hash"], tag: str = "") -> str:
    begin, end = markers(style, tag)
    if any(line.strip() in (begin, end) for line in body.splitlines()):
        raise BlockError("block body contains a marker line")
    lines = text.splitlines(keepends=True)  # only marker LINES count; a marker quoted in prose does not
    b = [i for i, ln in enumerate(lines) if ln.strip() == begin]
    e = [i for i, ln in enumerate(lines) if ln.strip() == end]
    if not b and not e:
        sep = "" if (not text or text.endswith("\n")) else "\n"
        gap = "\n" if text else ""
        return f"{text}{sep}{gap}{begin}\n{body}\n{end}\n"
    if len(b) != 1 or len(e) != 1 or b[0] > e[0]:
        raise BlockError("markers are duplicated, unbalanced or reversed; fix the file by hand")
    eol = "\r\n" if lines[b[0]].endswith("\r\n") else "\n"
    return "".join(lines[: b[0] + 1]) + body.replace("\n", eol) + eol + "".join(lines[e[0] :])
