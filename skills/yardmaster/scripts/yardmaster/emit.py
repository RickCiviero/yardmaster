"""Scalar emitters for the config formats Yardmaster writes. Every value is escaped for its target syntax, so
untrusted text can never add keys, items or lines (it is also screened earlier by schema.py: defence in depth)."""

import re
import unicodedata

_ESC = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f"}


def _quoted(s: str) -> str:
    # A double-quoted scalar valid as BOTH a YAML 1.2 and a TOML basic string: every control, format, separator,
    # surrogate and private-use character becomes \uXXXX so nothing can break a line or be mis-folded.
    out = []
    for ch in s:
        if ch in _ESC:
            out.append(_ESC[ch])
        elif unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp", "Cs", "Co", "Cn"):
            out.append(f"\\u{ord(ch):04x}" if ord(ch) <= 0xFFFF else f"\\U{ord(ch):08x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def yaml_str(s: str) -> str:
    return _quoted(s)


def toml_str(s: str) -> str:
    return _quoted(s)


_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>#|])")


def md_escape(s: str) -> str:
    """One line of inert Markdown text: newlines collapse to spaces, markup characters are backslash-escaped."""
    return _MD_SPECIAL.sub(r"\\\1", re.sub(r"\r\n|[\n\r  \x0b\x0c\x85]", " ", s))
