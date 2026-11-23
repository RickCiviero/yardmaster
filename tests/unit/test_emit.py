import re
import tomllib

import pytest
import yaml
from yardmaster.emit import md_escape, toml_str, yaml_str

HOSTILE = [
    ": x", "#c", "&a *a", "!!python/object:os.system", "\n- model: evil", "]]", "key: value\nother: v", "- ", "---", "...",
    "@x", "%TAG ! tag:x", "null", "true", "1e3", "~", " x", " ", "\x85", "﻿", 'quote"inside', "back\\slash",
    "😀 emoji", "tab\there", "ctl\x01\x7f", "'single'", "a: b: c", "{a: b}", "[1, 2]", "| literal", "> folded", "é ü ñ", "", " lead",
    "trail ", "line1\r\nline2", "\\u0041", "\\n", "x" * 5000,
]


@pytest.mark.parametrize("s", HOSTILE)
def test_yaml_roundtrip_hostile(s):
    assert yaml.safe_load(f"k: {yaml_str(s)}\n") == {"k": s}
    doc = yaml.safe_load(f"- model: {yaml_str('opus')}\n  when: {yaml_str(s)}\n- model: next\n")
    assert doc == [{"model": "opus", "when": s}, {"model": "next"}]  # a hostile value never adds keys or items


@pytest.mark.parametrize("s", HOSTILE)
def test_toml_roundtrip_hostile(s):
    assert tomllib.loads(f"k = {toml_str(s)}")["k"] == s
    assert tomllib.loads(f"[a]\nk = {toml_str(s)}\n[b]\nz = 1\n") == {"a": {"k": s}, "b": {"z": 1}}


def test_emitted_scalars_are_single_line():
    for s in HOSTILE:
        assert "\n" not in yaml_str(s) and "\n" not in toml_str(s)
        assert "\r" not in yaml_str(s) and " " not in yaml_str(s)


@pytest.mark.parametrize("s", HOSTILE)
def test_md_escape_neutralises_markup_and_newlines(s):
    out = md_escape(s)
    assert "\n" not in out and "\r" not in out
    for ch in "`*_[]<>#|":
        # an occurrence is safe only when preceded by an odd number of backslashes
        for m in re.finditer(re.escape(ch), out):
            backslashes = len(out[: m.start()]) - len(out[: m.start()].rstrip("\\"))
            assert backslashes % 2 == 1, (ch, out)


def test_md_escape_examples():
    assert md_escape("a *b* `c`\nd") == "a \\*b\\* \\`c\\` d"
    assert md_escape("<!-- x -->") == "\\<!-- x --\\>"
    assert md_escape("| a | b") == "\\| a \\| b"
    assert md_escape("back\\slash") == "back\\\\slash"
