"""The model catalog: which models each harness offers, and how strong each one is. It holds no prices.

Strength is a tier (light, standard, heavy, frontier). Within a tier, models are listed weakest first, and `choose` takes
the first allowed one. The file ships inside the package, so a user cannot add models to it."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .safe_io import read_text

TIERS = ("light", "standard", "heavy", "frontier")
SCHEMA = 2
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/]{0,63}$")
_MODEL_KEYS = {"id", "aliases", "tier", "notes"}


@dataclass(frozen=True)
class ModelInfo:
    id: str
    harness: str
    tier: str
    aliases: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class Catalog:
    def __init__(self, as_of: str, models: dict[str, list[ModelInfo]]):
        self.as_of, self._models = as_of, models

    def harnesses(self) -> list[str]:
        return list(self._models)

    def models(self, harness: str) -> list[ModelInfo]:
        return list(self._models.get(harness, []))

    def get(self, harness: str, name: str) -> ModelInfo | None:
        k = name.strip().lower().removeprefix("copilot/")
        for m in self._models.get(harness, []):
            if k == m.id.lower() or k in (a.lower() for a in m.aliases):
                return m
        return None

    def choose(self, harness: str, tier: str, deny: frozenset[str]) -> ModelInfo | None:
        """The weakest allowed model of `tier`. If none is allowed, the weakest of the next tier UP, never down."""
        denied = {d.lower() for d in deny}
        for t in TIERS[TIERS.index(tier):]:
            for m in self._models.get(harness, []):
                if m.tier == t and not ({m.id.lower(), *(a.lower() for a in m.aliases)} & denied):
                    return m
        return None


def _name(v: object, what: str) -> str:
    if not isinstance(v, str) or not _NAME.match(v):
        raise ValueError(f"catalog: bad {what}")
    return v


def load_catalog(path: Path) -> Catalog:
    try:
        doc = json.loads(read_text(Path(path)))
    except (OSError, ValueError, RecursionError) as e:
        raise ValueError(f"catalog: cannot read {Path(path).name}") from e
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or not isinstance(doc.get("harnesses"), dict):
        raise ValueError("catalog: unsupported schema")
    models: dict[str, list[ModelInfo]] = {}
    for h, hv in doc["harnesses"].items():
        if not isinstance(hv, dict) or not isinstance(hv.get("models"), list):
            raise ValueError(f"catalog: bad harness entry {h!r}")
        seen: set[str] = set()
        out: list[ModelInfo] = []
        for m in hv["models"]:
            if not isinstance(m, dict) or set(m) - _MODEL_KEYS:
                raise ValueError("catalog: a model entry has unknown keys")
            mid = _name(m.get("id"), "model id")
            aliases = tuple(_name(a, "alias") for a in m.get("aliases") or [])
            for n in (mid, *aliases):
                if n.lower() in seen:
                    raise ValueError(f"catalog: duplicate model name {n!r} in {h}")
                seen.add(n.lower())
            if m.get("tier") not in TIERS:
                raise ValueError(f"catalog: bad tier for {mid}")
            out.append(ModelInfo(mid, h, m["tier"], aliases, tuple(str(x) for x in m.get("notes") or [])))
        models[h] = out
    return Catalog(str(doc.get("as_of", "")), models)


def default_catalog() -> Catalog:
    """The catalog that ships inside the package."""
    return load_catalog(Path(__file__).with_name("models.json"))
