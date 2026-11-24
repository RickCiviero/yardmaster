"""The README's install commands are the ones the manifests are pinned to, and no doc link is dead."""

import re
from pathlib import Path

import pytest
from install_commands import INSTALL_COMMANDS

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
WIKI = ROOT / "docs" / "wiki"
PAGES = ["Home", "Meet-the-Yardmaster", "Quick-start", "How-it-works", "Supported-harnesses",
         "Security-and-compliance", "Models", "FAQ", "Contributing"]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)|<img[^>]+src=\"([^\"]+)\"")


def _install_lines() -> list[str]:
    blocks = re.findall(r"```[^\n]*\n(.*?)```", README.read_text(encoding="utf-8"), re.S)
    return [ln.strip() for b in blocks for ln in b.splitlines() if ln.strip().startswith(("/plugin", "npx skills"))]


def test_readme_documents_exactly_the_pinned_install_commands():
    assert sorted(_install_lines()) == sorted(INSTALL_COMMANDS)


def _targets(doc: Path):
    for m in LINK.finditer(doc.read_text(encoding="utf-8")):
        t = (m[1] or m[2]).split("#")[0]
        if t and not t.startswith(("http://", "https://", "mailto:")):
            yield t


def _resolves(doc: Path, target: str) -> bool:
    p = (doc.parent / target)
    return p.exists() or p.with_name(p.name + ".md").exists()


@pytest.mark.parametrize("doc", [README, *sorted(WIKI.glob("*.md"))], ids=lambda p: p.name)
def test_every_relative_link_resolves(doc):
    assert [t for t in _targets(doc) if not _resolves(doc, t)] == []


def test_the_wiki_has_every_page_and_home_links_each():
    assert sorted(p.stem for p in WIKI.glob("*.md")) == sorted(PAGES)
    home = {t for t in _targets(WIKI / "Home.md")}
    assert home >= set(PAGES) - {"Home"}


def test_the_readme_opens_with_the_logo_and_tagline_and_ends_with_the_licence():
    t = README.read_text(encoding="utf-8")
    assert t.index("assets/logo.svg") < t.index("Right job. Right track. Lowest fare.")
    assert [h for h in re.findall(r"^## (.+)$", t, re.M)] == [
        "Meet the Yardmaster", "What it does", "Install", "Quick start", "Supported harnesses", "Security",
        "Verify a release", "Contributing", "Licence"]
