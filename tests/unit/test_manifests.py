import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml
from install_commands import INSTALL_COMMANDS, REPO, URL
from yardmaster import __version__

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
GEMINI = ROOT / "gemini-extension.json"
COMMAND = ROOT / "commands" / "yardmaster.md"
PROMPT = ROOT / ".github" / "prompts" / "yardmaster.prompt.md"
FORBIDDEN = ("hooks", "allowed-tools", "allowedtools", "permissions", "mcpservers", "mcp_servers", "bypass", "autoapprove")


def _json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _front(p: Path) -> dict:
    text = p.read_text(encoding="utf-8")
    assert text.startswith("---\n"), p
    return yaml.safe_load(text.split("---\n")[1])


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k).lower()
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


def test_versions_are_all_the_package_version():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__
    assert _json(PLUGIN)["version"] == __version__
    assert _json(GEMINI)["version"] == __version__
    (entry,) = _json(MARKET)["plugins"]
    assert entry["version"] == __version__


def test_plugin_and_marketplace_identity():
    p, m = _json(PLUGIN), _json(MARKET)
    assert p["name"] == "yardmaster" and p["license"] == "MIT" and p["repository"] == URL and p["homepage"] == URL
    assert m["name"] == "yardmaster" and m["owner"]["name"] == "RickCiviero"
    (entry,) = m["plugins"]
    assert entry["name"] == "yardmaster" and entry["source"] == "./" and entry["description"]


def test_skill_the_plugin_ships_exists():
    assert (ROOT / "skills" / "yardmaster" / "SKILL.md").is_file()
    assert (ROOT / "skills" / "yardmaster" / "pricing.json").is_file()
    assert (ROOT / "skills" / "yardmaster" / "scripts" / "yardmaster.py").is_file()


def test_install_commands_match_the_manifests():
    assert f"/plugin marketplace add {REPO}" in INSTALL_COMMANDS
    plugin_name, market_name = _json(PLUGIN)["name"], _json(MARKET)["name"]
    assert f"/plugin install {plugin_name}@{market_name}" in INSTALL_COMMANDS
    assert all(c.startswith(("/plugin ", "npx skills add ")) for c in INSTALL_COMMANDS) and len(set(INSTALL_COMMANDS)) == len(INSTALL_COMMANDS)


@pytest.mark.parametrize("path", [PLUGIN, MARKET, GEMINI])
def test_manifests_declare_no_hooks_tools_permissions_or_servers(path):
    bad = [k for k in _walk_keys(_json(path)) if k.replace("-", "").replace("_", "") in {f.replace("-", "").replace("_", "") for f in FORBIDDEN}]
    assert not bad, f"{path.name} declares {bad}"


@pytest.mark.parametrize("path", [COMMAND, PROMPT])
def test_command_and_prompt_do_not_preapprove_anything(path):
    fm = _front(path)
    assert fm.get("description")
    assert not [k for k in fm if k.lower().replace("-", "").replace("_", "") in {"allowedtools", "tools", "hooks", "permissions"}]
    body = path.read_text(encoding="utf-8")
    assert "--apply" not in body  # applying is gated inside the skill, never baked into a shortcut


def test_command_routes_arguments_to_the_skill():
    body = COMMAND.read_text(encoding="utf-8")
    assert "yardmaster" in body and "$ARGUMENTS" in body
    for sub in ("ledger", "undo", "doctor"):
        assert sub in body
    assert re.search(r"skill", body, re.I)


def test_prompt_file_points_at_the_skill():
    body = PROMPT.read_text(encoding="utf-8")
    assert "SKILL.md" in body and "yardmaster" in body.lower()


def test_gemini_manifest_is_minimal_and_honest():
    g = _json(GEMINI)
    assert set(g) <= {"name", "version", "description"} and g["name"] == "yardmaster"
