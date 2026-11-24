"""Strict validation of everything the model hands back. The model is untrusted: anything not on the allow-list is
rejected, never repaired. Free-text fields are the injection surface, so they are screened for control characters,
fence/markup breakers, URLs and path-like sequences before any writer may render them."""

import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from .catalog import TIERS, Catalog

SLUG = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
OUTCOMES = ("ok", "struggled", "failed")
_BANNED = ("`", "<<<", "://", "../", "..\\", "~/", "<!--", "-->")
_DRIVE = re.compile(r"[A-Za-z]:[\\/]")
# shortcut: a heuristic, not a proof. Model-written text ends up in files agents read later (CLAUDE.md, subagents), so
# text that addresses an assistant or names a shell command is refused; the user's review of the diff is the real gate.
_INSTRUCTION = re.compile(
    r"(?i)\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,60}\b(instructions?|prompts?|rules?|above|previous|everything|safeguards?|guardrails?)\b"
    r"|system prompt|developer mode|\byou (must|are now|should now)\b|\bexfiltrat\w*"
    r"|\brm\s+-rf\b|\b(sudo|powershell|wget|curl|chmod)\b|\bbash\s+-c\b"
    r"|\bapprove\b[^.\n]{0,30}\b(diff|plan|change|apply)\w*|\bwithout (asking|confirmation|approval)\b"
    r"|javascript:|<\s*script|\beval\s*\(|\bexec\s*\("
)
VERDICT_KEYS = {"chat_id", "task_group", "task_summary", "model_used", "outcome", "sufficient_tier",
                "weakest_sufficient_model", "confidence", "reason"}
GROUP_KEYS = {"name", "tier", "when", "examples", "chats", "prefer"}
PLAN_KEYS = {"version", "description", "groups"}


class ValidationError(Exception):
    def __init__(self, msg: str, path: str = ""):
        super().__init__(f"{path or '/'}: {msg}")
        self.path = path


def _dict(v: object, keys: set[str], path: str) -> dict:
    if not isinstance(v, dict):
        raise ValidationError("must be an object", path)
    if extra := set(v) - keys:
        raise ValidationError(f"unknown keys {sorted(map(str, extra))}", path)
    if missing := keys - set(v):
        raise ValidationError(f"missing keys {sorted(missing)}", path)
    return v


def _text(v: object, path: str, *, max_chars: int, max_words: int | None = None, allow_empty: bool = False) -> str:
    if not isinstance(v, str):
        raise ValidationError("must be a string", path)
    if (not v.strip() and not allow_empty) or len(v) > max_chars:
        raise ValidationError(f"must be 1..{max_chars} characters", path)
    if max_words is not None and len(v.split()) > max_words:
        raise ValidationError(f"must be at most {max_words} words", path)
    if any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp", "Cs") for c in v):
        raise ValidationError("contains control or invisible characters", path)
    if any(b in v for b in _BANNED) or _DRIVE.search(v):
        raise ValidationError("contains a forbidden sequence (markup, URL or path)", path)
    if _INSTRUCTION.search(v):
        raise ValidationError("reads like an instruction to an assistant or a shell command; describe the work neutrally", path)
    return v


def _slug(v: object, path: str) -> str:
    if not isinstance(v, str) or not SLUG.match(v):
        raise ValidationError("must be a lowercase slug (2-32 chars: a-z, 0-9, -)", path)
    return v


def _enum(v: object, allowed: tuple[str, ...], path: str) -> str:
    if v not in allowed or not isinstance(v, str):
        raise ValidationError(f"must be one of {list(allowed)}", path)
    return v


def _int(v: object, path: str, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ValidationError(f"must be an integer {lo}..{hi}", path)
    return v


@dataclass(frozen=True)
class Verdict:
    chat_id: str
    task_group: str
    task_summary: str
    model_used: str
    outcome: str
    sufficient_tier: str
    weakest_sufficient_model: str
    confidence: float
    reason: str


def validate_verdicts(obj: object, *, manifest_ids: set[str], catalog: Catalog) -> list[Verdict]:
    if not isinstance(obj, list):
        raise ValidationError("must be a list of verdicts")
    out: list[Verdict] = []
    seen: set[str] = set()
    for i, raw in enumerate(obj):
        p = f"/{i}"
        d = _dict(raw, VERDICT_KEYS, p)
        cid = d["chat_id"]
        if not isinstance(cid, str) or cid not in manifest_ids:
            raise ValidationError("unknown chat id", f"{p}/chat_id")
        if cid in seen:
            raise ValidationError("duplicate verdict for chat", f"{p}/chat_id")
        seen.add(cid)
        conf = d["confidence"]
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not math.isfinite(conf) or not 0 <= conf <= 1:
            raise ValidationError("must be a number 0..1", f"{p}/confidence")
        model = _text(d["weakest_sufficient_model"], f"{p}/weakest_sufficient_model", max_chars=64)
        if catalog.get(cid.partition(":")[0], model) is None:
            raise ValidationError("not a known model for this chat's harness", f"{p}/weakest_sufficient_model")
        out.append(Verdict(
            cid, _slug(d["task_group"], f"{p}/task_group"),
            _text(d["task_summary"], f"{p}/task_summary", max_chars=200, max_words=25),
            _text(d["model_used"], f"{p}/model_used", max_chars=80), _enum(d["outcome"], OUTCOMES, f"{p}/outcome"),
            _enum(d["sufficient_tier"], TIERS, f"{p}/sufficient_tier"), model, float(conf),
            _text(d["reason"], f"{p}/reason", max_chars=240, max_words=30)))
    if missing := manifest_ids - seen:
        raise ValidationError(f"missing verdicts for {len(missing)} chat(s), e.g. {sorted(missing)[0]}")
    return out


@dataclass(frozen=True)
class Group:
    name: str
    tier: str
    when: str
    examples: list[str]
    chats: int
    prefer: dict[str, str]


@dataclass(frozen=True)
class Plan:
    version: int
    description: str
    groups: list[Group]


def validate_plan(obj: object, *, catalog: Catalog) -> Plan:
    d = _dict(obj, PLAN_KEYS, "")
    if d["version"] != 1 or isinstance(d["version"], bool):
        raise ValidationError("version must be 1", "/version")
    desc = _text(d["description"], "/description", max_chars=120)
    if not isinstance(d["groups"], list) or not 1 <= len(d["groups"]) <= 12:
        raise ValidationError("must be a list of 1..12 groups", "/groups")
    groups: list[Group] = []
    names: set[str] = set()
    for i, raw in enumerate(d["groups"]):
        p = f"/groups/{i}"
        g = _dict(raw, GROUP_KEYS, p)
        name = _slug(g["name"], f"{p}/name")
        if name in names:
            raise ValidationError("duplicate group name", f"{p}/name")
        names.add(name)
        tier = _enum(g["tier"], TIERS, f"{p}/tier")
        when = _text(g["when"], f"{p}/when", max_chars=300)
        ex = g["examples"]
        if not isinstance(ex, list) or len(ex) > 3:
            raise ValidationError("must be a list of at most 3 examples", f"{p}/examples")
        examples = [_text(e, f"{p}/examples/{j}", max_chars=80) for j, e in enumerate(ex)]
        chats = _int(g["chats"], f"{p}/chats", 0, 10**6)
        if not isinstance(g["prefer"], dict):
            raise ValidationError("must be an object", f"{p}/prefer")
        prefer: dict[str, str] = {}
        for h, m in g["prefer"].items():
            info = catalog.get(h, m) if isinstance(h, str) and isinstance(m, str) else None
            if info is None or TIERS.index(info.tier) < TIERS.index(tier):
                raise ValidationError("must name a known model of this tier or higher", f"{p}/prefer/{h}")
            prefer[h] = m
        groups.append(Group(name, tier, when, examples, chats, prefer))
    return Plan(1, desc, groups)


def load_manifest_ids(manifest: Mapping) -> set[str]:
    ids = manifest.get("chat_ids") if isinstance(manifest, Mapping) else None
    if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
        raise ValidationError("manifest has no chat_ids")
    return set(ids)
