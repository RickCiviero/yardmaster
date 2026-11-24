"""The wheel and sdist must carry every runtime package, the model catalog and the `yardmaster` command."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "skills" / "yardmaster" / "scripts" / "yardmaster"


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_command_points_at_the_cli():
    assert _pyproject()["project"]["scripts"]["yardmaster"] == "yardmaster.cli:main"


def test_every_runtime_package_is_listed_in_the_build():
    listed = set(_pyproject()["tool"]["setuptools"]["packages"])
    found = {"yardmaster" + "".join("." + part for part in d.relative_to(PKG).parts) for d in (p.parent for p in PKG.rglob("__init__.py"))}
    assert found == listed, found ^ listed


def test_the_catalog_ships_inside_the_package():
    assert _pyproject()["tool"]["setuptools"]["package-data"]["yardmaster"] == ["models.json"]
    assert (PKG / "models.json").is_file()


def test_metadata_is_complete_and_has_no_runtime_dependencies():
    doc = _pyproject()
    assert doc["build-system"]["build-backend"] == "setuptools.build_meta"
    project = doc["project"]
    assert project["license"] == "MIT" and project["license-files"] == ["LICENSE"] and project["readme"] == "README.md"
    assert project["requires-python"] == ">=3.11" and project["dependencies"] == []
    assert project["urls"]["Homepage"] == "https://github.com/RickCiviero/yardmaster"
