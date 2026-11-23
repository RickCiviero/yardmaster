import re
import time
from collections import Counter

import pytest
from secrets_corpus import SECRETS, tok
from yardmaster.redact import PII_RULES, RULES, redact


def _leaks(secret: str, redacted: str, n: int = 8) -> list[str]:
    return [secret[i : i + n] for i in range(len(secret) - n + 1) if secret[i : i + n] in redacted]


@pytest.mark.parametrize("key", sorted(SECRETS))
def test_each_rule_redacts_its_fixture(key):
    secret = SECRETS[key]
    out, counts = redact(f"before {secret} after")
    assert _leaks(secret, out) == []
    assert out.startswith("before ") and out.endswith(" after")
    assert key.split("#")[0] in counts, (key, dict(counts))


def test_every_rule_has_a_fixture():
    assert {r.name for r in RULES} <= {k.split("#")[0] for k in SECRETS}


CODE = '''
import uuid, hashlib
from pathlib import Path

DEFAULT_ID = "3f2504e0-4f5c-11d0-9d64-00a0c91e6bf6"
COMMIT = "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3"
DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SPEC = Path("docs/superpowers/specs/2026-11-23-yardmaster-design.md")
LONG_PATH = "skills/yardmaster/scripts/yardmaster/collectors/vscode_copilot.py"

def total(xs: list[int]) -> int:
    return sum(x for x in xs if x > 0)

export const retries = 3;  // see https://example.com/docs/retry-policy
const maxTokens = 4096;
'''


def test_no_false_positive_on_code():
    out, counts = redact(CODE)
    assert out == CODE
    assert not counts


def test_redaction_keeps_surrounding_text_and_counts():
    a, b = SECRETS["github-pat"], "gh" + "p_" + tok(36)
    out, counts = redact(f"one {a} two {b} three")
    assert out.count("[REDACTED:github-pat]") == 2
    assert counts == Counter({"github-pat": 2})
    assert out.startswith("one ") and " two " in out and out.endswith(" three")


def test_pii_optional():
    text = "mail a.b@example.com from 10.0.0.1 in C:\\Users\\José\\proj and /home/rick/x and /Users/ann/y"
    same, c0 = redact(text)
    assert same == text and not c0
    out, counts = redact(text, pii=True)
    for gone in ("a.b@example.com", "10.0.0.1", "José", "rick", "ann"):
        assert gone not in out
    assert "~\\proj" in out and "~/x" in out and "~/y" in out
    assert {"email", "ipv4", "home-path"} <= set(counts)


def test_high_entropy_token_redacted():
    blob = tok(48, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/")
    out, counts = redact(f"x {blob} y")
    assert blob not in out and counts["high-entropy"] == 1


def test_long_lines_are_windowed_and_still_redacted():
    secret = SECRETS["github-pat"]
    line = ("word " * 9990) + secret + (" word" * 9990)  # one ~100k-char line
    out, counts = redact(line)
    assert secret not in out and counts["github-pat"] == 1


def test_secret_straddling_window_boundary_is_redacted():
    secret = SECRETS["github-pat"]
    for pad in (9960, 9970, 9980, 9990):  # place the token across the 10_000-char window edge
        out, _ = redact(("a " * (pad // 2)) + secret + (" b" * 12000))
        assert secret not in out


@pytest.mark.parametrize("rule", [*RULES, *PII_RULES], ids=lambda r: r.name)
def test_redos_linear(rule):
    for bad in ("a" * 50_000 + "!", "=" * 50_000, "-" * 50_000, "a=" * 25_000, "A.B-" * 12_500):
        t = time.perf_counter()
        rule.pattern.findall(bad)
        assert time.perf_counter() - t < 0.5, (rule.name, bad[:6])


def test_redact_is_fast_on_adversarial_input():
    t = time.perf_counter()
    redact("eyJa-" * 40_000 + "\n" + "password " + " " * 50_000)
    assert time.perf_counter() - t < 5


def test_rules_are_compiled_patterns_with_unique_names():
    names = [r.name for r in RULES]
    assert len(names) == len(set(names))
    assert all(isinstance(r.pattern, re.Pattern) for r in RULES)
