from pathlib import Path

import pytest
from yardmaster import writers
from yardmaster.pricing import load_pricing
from yardmaster.resolve import ResolvedGroup, resolve_plan
from yardmaster.schema import Group, Plan

PRICING = load_pricing(Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "pricing.json")
GOLDEN = Path(__file__).parent / "golden"

PLAN = Plan(
    1,
    "Opus to plan, Sonnet to build, a light model for quick questions.",
    [
        Group("deep-planning", "frontier", "Planning difficult multi-step work, such as architecture or migration design.",
              ["a migration plan", "an architecture review"], 5, {}),
        Group("build-and-fix", "heavy", "Building or changing code over many steps, such as a feature, a bug fix, or a refactor.",
              ["a new endpoint", "a failing test"], 40, {}),
        Group("quick-questions", "light", "Quick answers and small chores, such as where something is or what a setting does.",
              ["where is the config", "what a flag does"], 60, {}),
    ],
)


@pytest.fixture(autouse=True)
def fixed_date(monkeypatch):
    monkeypatch.setattr(writers, "today", lambda: "2026-11-23")


@pytest.fixture
def resolved():
    def _resolve(harness: str, deny=frozenset()) -> list[ResolvedGroup]:
        return resolve_plan(PLAN, harness, PRICING, deny)

    return _resolve


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path / "home"), "USERPROFILE": str(tmp_path / "home")}


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    return p


def apply(changes) -> None:
    for c in changes:
        c.path.parent.mkdir(parents=True, exist_ok=True)
        c.path.write_text(c.new, encoding="utf-8", newline="\n")


def rel(changes) -> dict[str, str]:
    """{posix path relative to its root: new text}"""
    return {c.path.relative_to(c.root).as_posix(): c.new for c in changes}


def check_golden(name: str, changes, root_label: str = "") -> None:
    for relpath, text in rel(changes).items():
        g = GOLDEN / name / relpath
        assert g.is_file(), f"missing golden {g}"
        assert text == g.read_text(encoding="utf-8"), f"{name}/{relpath} differs from its golden file"
    assert sorted(rel(changes)) == sorted(p.relative_to(GOLDEN / name).as_posix() for p in (GOLDEN / name).rglob("*") if p.is_file())
