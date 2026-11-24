"""Model price/tier table. Ships signed with each release; a local file may adjust prices but never add models."""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from .safe_io import read_text

TIERS = ("light", "standard", "heavy", "frontier")
UNITS = ("credit", "usd_per_mtok")
PRICE_KEYS = ("input", "output", "cached", "multiplier")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/]{0,63}$")


@dataclass(frozen=True)
class ModelInfo:
    id: str
    harness: str
    tier: str
    input: float | None
    output: float | None
    cached: float | None
    multiplier: float | None
    aliases: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def unit_cost(self, tokens_in: int, tokens_out: int, tokens_cached: int) -> float:
        """USD for token-priced models; credits PER REQUEST (tokens ignored) for credit-priced ones."""
        if self.input is None:
            return self.multiplier or 0.0
        return (tokens_in * self.input + tokens_out * (self.output or 0.0) + tokens_cached * (self.cached or 0.0)) / 1e6

    @property
    def sort_key(self) -> tuple[float, float]:
        return (self.multiplier or 0.0, 0.0) if self.input is None else (self.output or 0.0, self.input)


class Pricing:
    def __init__(self, as_of: str, verified: bool, units: dict[str, str], models: dict[str, list[ModelInfo]]):
        self.as_of, self.verified, self.units, self._models = as_of, verified, units, models

    def models(self, harness: str) -> list[ModelInfo]:
        return list(self._models.get(harness, []))

    def get(self, harness: str, name: str) -> ModelInfo | None:
        k = name.strip().lower()
        k = k.removeprefix("copilot/")
        for m in self._models.get(harness, []):
            if k == m.id.lower() or k in (a.lower() for a in m.aliases):
                return m
        return None

    def tier_of(self, harness: str, name: str) -> str | None:
        m = self.get(harness, name)
        return m.tier if m else None

    def cheapest(self, harness: str, tier: str, deny: frozenset[str]) -> ModelInfo | None:
        """Cheapest allowed model of `tier`; if none is allowed, of the next tier UP (never down)."""
        denied = {d.lower() for d in deny}
        for t in TIERS[TIERS.index(tier) :]:
            ok = [
                m
                for m in self._models.get(harness, [])
                if m.tier == t and not ({m.id.lower(), *(a.lower() for a in m.aliases)} & denied)
            ]
            if ok:
                return min(ok, key=lambda m: m.sort_key)
        return None


def _num(v: object, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        raise ValueError(f"pricing: {what} must be a finite number >= 0")
    return float(v)


def _opt(v: object, what: str) -> float | None:
    return None if v is None else _num(v, what)


def _name(v: object, what: str) -> str:
    if not isinstance(v, str) or not _NAME.match(v):
        raise ValueError(f"pricing: bad {what}")
    return v


def _load_json(path: Path) -> dict:
    try:
        doc = json.loads(read_text(path))
    except (OSError, ValueError, RecursionError) as e:
        raise ValueError(f"pricing: cannot read {path.name}") from e
    if not isinstance(doc, dict):
        raise ValueError(f"pricing: {path.name} must be an object")
    return doc


def _apply_local(base: dict, local: dict) -> None:
    for h, hv in (local.get("harnesses") or {}).items():
        base_h = (base.get("harnesses") or {}).get(h)
        if not isinstance(base_h, dict) or not isinstance(hv, dict):
            continue
        by_id = {m.get("id"): m for m in base_h.get("models") or [] if isinstance(m, dict)}
        for lm in hv.get("models") or []:
            if isinstance(lm, dict) and lm.get("id") in by_id:
                by_id[lm["id"]].update({k: lm[k] for k in PRICE_KEYS if k in lm})  # prices only, never tier/id


def load_pricing(path: Path, local: Path | None = None) -> Pricing:
    doc = _load_json(Path(path))
    if local is not None and Path(local).is_file():
        _apply_local(doc, _load_json(Path(local)))
    if doc.get("schema") != 1 or not isinstance(doc.get("harnesses"), dict):
        raise ValueError("pricing: unsupported schema")
    units: dict[str, str] = {}
    models: dict[str, list[ModelInfo]] = {}
    for h, hv in doc["harnesses"].items():
        if not isinstance(hv, dict) or hv.get("unit") not in UNITS or not isinstance(hv.get("models"), list):
            raise ValueError(f"pricing: bad harness entry {h!r}")
        units[h], seen, out = hv["unit"], set(), []
        for m in hv["models"]:
            if not isinstance(m, dict):
                raise ValueError("pricing: model entry must be an object")
            mid = _name(m.get("id"), "model id")
            aliases = tuple(_name(a, "alias") for a in m.get("aliases") or [])
            for n in (mid, *aliases):
                if n.lower() in seen:
                    raise ValueError(f"pricing: duplicate model name {n!r} in {h}")
                seen.add(n.lower())
            if m.get("tier") not in TIERS:
                raise ValueError(f"pricing: bad tier for {mid}")
            if hv["unit"] == "credit":
                mult = _num(m.get("multiplier"), f"{mid}.multiplier")
                notes = tuple(map(str, m.get("notes") or []))
                info = ModelInfo(mid, h, m["tier"], None, None, None, mult, aliases, notes)
            else:
                info = ModelInfo(
                    mid, h, m["tier"], _num(m.get("input"), f"{mid}.input"), _num(m.get("output"), f"{mid}.output"),
                    _num(m.get("cached"), f"{mid}.cached"), _opt(m.get("multiplier"), f"{mid}.multiplier"),
                    aliases, tuple(map(str, m.get("notes") or [])),
                )
            out.append(info)
        models[h] = out
    return Pricing(str(doc.get("as_of", "")), doc.get("verified") is True, units, models)


def default_pricing(env, platform) -> Pricing:
    """The shipped pricing.json plus the user's local price overrides (prices only)."""
    from . import paths

    shipped = Path(__file__).resolve().parents[2] / "pricing.json"
    return load_pricing(shipped, paths.config_dir(env, platform) / "pricing.local.json")
