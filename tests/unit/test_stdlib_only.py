from pathlib import Path

import pytest
from check_stdlib_only import check, main

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "skills" / "yardmaster" / "scripts"


def test_the_shipped_runtime_is_stdlib_only_and_clean():
    assert check(RUNTIME) == []
    assert main([str(RUNTIME)]) == 0


@pytest.mark.parametrize(
    ("code", "needle"),
    [
        ("import requests\n", "requests"),
        ("from yaml import safe_load\n", "yaml"),
        ("import numpy as np\n", "numpy"),
        ("import subprocess\n", "subprocess"),
        ("import socket\n", "socket"),
        ("from urllib.request import urlopen\n", "urllib.request"),
        ("import urllib.request\n", "urllib.request"),
        ("import http.client\n", "http"),
        ("import ctypes\n", "ctypes"),
        ("import pickle\n", "pickle"),
        ("import marshal\n", "marshal"),
        ("import multiprocessing\n", "multiprocessing"),
        ("import smtplib\n", "smtplib"),
        ("eval('1+1')\n", "eval"),
        ("exec('x=1')\n", "exec"),
        ("__import__('os')\n", "__import__"),
        ("import os\nos.system('ls')\n", "os.system"),
        ("import os\nos.popen('ls')\n", "os.popen"),
        ("def f():\n    import subprocess\n", "subprocess"),
    ],
)
def test_planted_violations_are_caught(tmp_path, code, needle):
    (tmp_path / "bad.py").write_text(code)
    problems = check(tmp_path)
    assert problems and any(needle in p for p in problems), problems
    assert main([str(tmp_path)]) == 1


def test_allowed_imports_pass(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("from . import sibling\nfrom .sibling import x\n")
    (tmp_path / "pkg" / "sibling.py").write_text(
        "import json, os, re, tomllib, sqlite3, tempfile, hashlib\nfrom urllib.parse import unquote\nfrom yardmaster.safe_io import x\nx = 1\n"
    )
    assert check(tmp_path) == []


def test_syntax_errors_are_reported_not_crashed(tmp_path):
    (tmp_path / "broken.py").write_text("def (:\n")
    assert any("syntax" in p.lower() for p in check(tmp_path))
