"""User config + admin policy. The merge only ever NARROWS what policy allows."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .safe_io import read_text

DEFAULT_MAX_BATCHES = 40
KEYS = ("deny_models", "harnesses", "redact_pii", "max_batches")


@dataclass
class Settings:
    deny_models: frozenset[str]
    harnesses: frozenset[str] | None  # None = every harness
    redact_pii: bool
    max_batches: int
    sources: dict[str, str]  # key -> default | policy | config | policy+config


def _read(path: Path, label: str) -> dict:
    if not path.is_file():
        return {}
    try:
        data = tomllib.loads(read_text(path))
    except (tomllib.TOMLDecodeError, OSError, UnicodeError) as e:
        raise ValueError(f"{label}: cannot read {path}") from e
    for k, v in data.items():
        if k not in KEYS:
            raise ValueError(f"{label}: unknown key {k!r}")
        ok = {
            "deny_models": isinstance(v, list) and all(isinstance(x, str) for x in v),
            "harnesses": isinstance(v, list) and all(isinstance(x, str) for x in v),
            "redact_pii": isinstance(v, bool),
            "max_batches": isinstance(v, int) and not isinstance(v, bool) and v >= 1,
        }[k]
        if not ok:
            raise ValueError(f"{label}: bad value for {k!r}")
    return data


def load_settings(
    env: Mapping[str, str], platform: str, *, policy: Path | None = None, config: Path | None = None
) -> Settings:
    # No env var may redirect the policy file: it must not be replaceable by the user it constrains.
    pol = _read(policy or paths.policy_file(env, platform), "policy file")
    cfg = _read(config or paths.config_dir(env, platform) / "config.toml", "config file")

    def src(key: str) -> str:
        return "+".join(n for n, d in (("policy", pol), ("config", cfg)) if key in d) or "default"

    harnesses = [frozenset(d["harnesses"]) for d in (pol, cfg) if "harnesses" in d]
    batches = [d["max_batches"] for d in (pol, cfg) if "max_batches" in d]
    return Settings(
        deny_models=frozenset(pol.get("deny_models", [])) | frozenset(cfg.get("deny_models", [])),
        harnesses=frozenset.intersection(*harnesses) if harnesses else None,
        redact_pii=bool(pol.get("redact_pii") or cfg.get("redact_pii")),
        max_batches=min(batches) if batches else DEFAULT_MAX_BATCHES,
        sources={k: src(k) for k in KEYS},
    )
