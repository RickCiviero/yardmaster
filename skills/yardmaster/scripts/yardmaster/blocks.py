"""Edit only a marked block inside a shared file (CLAUDE.md, AGENTS.md, config.toml); never touch the rest."""

from typing import Literal

MARKERS = {
    "md": ("<!-- yardmaster:begin v1 -->", "<!-- yardmaster:end -->"),
    "hash": ("# yardmaster:begin v1", "# yardmaster:end"),
}


class BlockError(Exception):
    pass


def replace_block(text: str, body: str, *, style: Literal["md", "hash"]) -> str:
    if style not in MARKERS:
        raise ValueError(f"unknown block style {style!r}")
    begin, end = MARKERS[style]
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
