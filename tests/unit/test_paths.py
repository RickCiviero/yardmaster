from pathlib import Path

import pytest
from yardmaster import paths


@pytest.fixture
def env(tmp_path):
    return {
        "HOME": str(tmp_path / "h"),
        "USERPROFILE": str(tmp_path / "h"),
        "APPDATA": str(tmp_path / "roam"),
        "LOCALAPPDATA": str(tmp_path / "local"),
        "XDG_CONFIG_HOME": str(tmp_path / "xc"),
        "XDG_STATE_HOME": str(tmp_path / "xs"),
        "ProgramData": str(tmp_path / "pd"),
    }


def test_config_and_state_dirs_per_platform(env, tmp_path):
    h = tmp_path / "h"
    assert paths.config_dir(env, "win32") == tmp_path / "roam" / "yardmaster"
    assert paths.config_dir(env, "darwin") == h / "Library" / "Application Support" / "yardmaster"
    assert paths.config_dir(env, "linux") == tmp_path / "xc" / "yardmaster"
    assert paths.state_dir(env, "win32") == tmp_path / "local" / "yardmaster"
    assert paths.state_dir(env, "darwin") == (
        h / "Library" / "Application Support" / "yardmaster" / "state"
    )
    assert paths.state_dir(env, "linux") == tmp_path / "xs" / "yardmaster"


def test_defaults_without_xdg(tmp_path):
    env = {"HOME": str(tmp_path)}
    assert paths.config_dir(env, "linux") == tmp_path / ".config" / "yardmaster"
    assert paths.state_dir(env, "linux") == tmp_path / ".local" / "state" / "yardmaster"


def test_policy_file_per_platform(env, tmp_path):
    assert paths.policy_file(env, "win32") == tmp_path / "pd" / "yardmaster" / "policy.toml"
    assert paths.policy_file(env, "darwin") == Path(
        "/Library/Application Support/yardmaster/policy.toml"
    )
    assert paths.policy_file(env, "linux") == Path("/etc/yardmaster/policy.toml")


@pytest.mark.parametrize(
    ("platform", "base_key", "sub"),
    [("win32", "APPDATA", ""), ("linux", "XDG_CONFIG_HOME", "")],
)
def test_vscode_user_dirs_existing_only(env, platform, base_key, sub):
    base = Path(env[base_key])
    (base / "Code" / "User").mkdir(parents=True)
    (base / "Code - Insiders" / "User").mkdir(parents=True)
    (base / "Cursor" / "User").mkdir(parents=True)
    got = paths.vscode_user_dirs(env, platform)
    assert got == [base / "Code" / "User", base / "Code - Insiders" / "User"]


def test_vscode_user_dirs_darwin_and_missing(env, tmp_path):
    assert paths.vscode_user_dirs(env, "darwin") == []
    u = tmp_path / "h" / "Library" / "Application Support" / "Code" / "User"
    u.mkdir(parents=True)
    assert paths.vscode_user_dirs(env, "darwin") == [u]
