"""Secret and PII redaction. Runs BEFORE anything is batched or sent to a model.

Every quantifier is bounded, so no pattern can backtrack catastrophically (tested in test_redact.py).
Over-redaction is the accepted failure mode; a leaked secret is not.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

LINE_LIMIT = 10_000
OVERLAP = 200
ENTROPY_MIN = 4.5  # shortcut: paths/prose score ~4.0-4.3, random base64/alnum ~4.7+; tune with real data
_B64 = r"[A-Za-z0-9+/_\-=]"


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]


def _r(name: str, pattern: str, flags: int = 0) -> Rule:
    return Rule(name, re.compile(pattern, flags))


# Order matters only for naming: when spans overlap the earlier rule names the merged span.
RULES: tuple[Rule, ...] = (
    _r("private-key-block", r"-----BEGIN [A-Z ]{0,30}PRIVATE KEY-----[A-Za-z0-9+/=\s]{0,20000}(?:-----END [A-Z ]{0,30}PRIVATE KEY-----)?"),
    _r("aws-access-key", r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b"),
    _r("aws-secret", r"\baws_?secret_?access_?key\b\s{0,5}[:=]\s{0,5}['\"]?[A-Za-z0-9/+=]{40}", re.I),
    _r("gcp-api-key", r"\bAIza[0-9A-Za-z_\-]{35}"),
    _r("azure-storage-key", r"AccountKey=[A-Za-z0-9+/=]{40,1024}", re.I),
    _r("github-pat", r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})\b"),
    _r("gitlab-pat", r"\bglpat-[A-Za-z0-9_\-]{20,255}"),
    _r("slack-token", r"\bxox[abprs]-[A-Za-z0-9\-]{10,255}"),
    _r("slack-webhook", r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,255}"),
    _r("stripe-key", r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,255}"),
    _r("anthropic-key", r"\bsk-ant-[A-Za-z0-9_\-]{20,1024}"),
    _r("openai-key", r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,1024}"),
    _r("google-oauth", r"\bya29\.[A-Za-z0-9_\-]{20,1024}"),
    _r("jwt", r"\beyJ[A-Za-z0-9_\-]{8,2000}\.eyJ[A-Za-z0-9_\-]{8,2000}\.[A-Za-z0-9_\-]{8,2000}"),
    _r("npm-token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    _r("pypi-token", r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_\-]{50,1024}"),
    _r("url-credentials", r"\b[a-z][a-z0-9+.\-]{1,20}://[^\s:/@]{1,100}:[^\s/@]{1,200}@[^\s'\"`<>]{1,300}"),
    _r("connection-string", r"\b(?:server|data source|host)\s{0,5}=[^;\n]{1,200};[^\n]{0,300}?\b(?:password|pwd)\s{0,5}=\s{0,5}[^;\s'\"]{1,200}", re.I),
    _r("auth-header", r"\b(?:bearer|basic)\s{1,5}[A-Za-z0-9._~+/\-]{16,2000}=*", re.I),
    _r("generic-secret", r"(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|auth)[\w\-]{0,20}\s{0,5}[:=]\s{0,5}['\"]?[^\s'\"`,;]{6,500}", re.I),
)

PII_RULES: tuple[Rule, ...] = (
    _r("email", r"\b[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,255}\.[A-Za-z]{2,24}\b"),
    _r("ipv4", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # shortcut: full-form IPv6 only; compressed forms collide with times/hex, upgrade if reviewers ask
    _r("ipv6", r"\b(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}\b"),
    _r("home-path", r"(?:[A-Za-z]:\\Users\\|/Users/|/home/)[^\\/\s]{1,64}", re.I),
)

_TOKEN = re.compile(rf"{_B64}{{32,1024}}")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_HEX = re.compile(r"[0-9a-fA-F]{1,64}")
_LONG_LINE = re.compile(rf"[^\n]{{{LINE_LIMIT + 1}}}")


def _entropy(s: str) -> float:
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def _looks_secret(tok: str) -> bool:
    if _UUID.fullmatch(tok) or _HEX.fullmatch(tok):
        return False
    if not (any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok)):
        return False
    if sum(c in "/_-" for c in tok) / len(tok) >= 0.2:
        return False
    return _entropy(tok) >= ENTROPY_MIN


def _windows(text: str):
    if not _LONG_LINE.search(text):
        yield 0, text
        return
    step = LINE_LIMIT - OVERLAP
    for off in range(0, len(text), step):
        yield off, text[off : off + LINE_LIMIT]
        if off + LINE_LIMIT >= len(text):
            return


def redact(text: str, *, pii: bool = False) -> tuple[str, Counter[str]]:
    text = text.encode("utf-8", "replace").decode("utf-8")  # lone surrogates from hostile JSON would crash every writer
    rules = RULES + (PII_RULES if pii else ())
    entropy_idx = len(RULES)
    spans: list[tuple[int, int, int, str]] = []  # (start, end, priority, name)
    for off, win in _windows(text):
        for i, rule in enumerate(rules):
            for m in rule.pattern.finditer(win):
                spans.append((off + m.start(), off + m.end(), i if i < entropy_idx else i + 1, rule.name))
        for m in _TOKEN.finditer(win):
            if _looks_secret(m.group()):
                spans.append((off + m.start(), off + m.end(), entropy_idx, "high-entropy"))
    spans.sort(key=lambda s: (s[0], s[2]))

    out: list[str] = []
    counts: Counter[str] = Counter()
    pos = 0
    cur: list | None = None  # merged [start, end, priority, name]; the most specific rule names it
    for start, end, prio, name in [*spans, (len(text) + 1, len(text) + 1, 0, "")]:
        if cur and start < cur[1]:
            cur[1] = max(cur[1], end)
            if prio < cur[2]:
                cur[2], cur[3] = prio, name
            continue
        if cur:
            out.append(text[pos : cur[0]])
            out.append("~" if cur[3] == "home-path" else f"[REDACTED:{cur[3]}]")
            counts[cur[3]] += 1
            pos = cur[1]
        cur = [start, end, prio, name]
    out.append(text[pos:])
    return "".join(out), counts
