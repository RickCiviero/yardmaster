"""Per-OS locations for Yardmaster's own files and for the harnesses it reads. Pure: takes env + platform."""

from collections.abc import Mapping
from pathlib import Path


def _home(env: Mapping[str, str]) -> Path:
    return Path(env.get("HOME") or env.get("USERPROFILE") or Path.home())


def _user_config_base(env: Mapping[str, str], platform: str) -> Path:
    home = _home(env)
    if platform.startswith("win"):
        return Path(env.get("APPDATA") or home / "AppData" / "Roaming")
    if platform == "darwin":
        return home / "Library" / "Application Support"
    return Path(env.get("XDG_CONFIG_HOME") or home / ".config")


def config_dir(env: Mapping[str, str], platform: str) -> Path:
    return _user_config_base(env, platform) / "yardmaster"


def state_dir(env: Mapping[str, str], platform: str) -> Path:
    home = _home(env)
    if platform.startswith("win"):
        return Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local") / "yardmaster"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "yardmaster" / "state"
    return Path(env.get("XDG_STATE_HOME") or home / ".local" / "state") / "yardmaster"


def policy_file(env: Mapping[str, str], platform: str) -> Path:
    if platform.startswith("win"):
        return Path(env.get("ProgramData") or r"C:\ProgramData") / "yardmaster" / "policy.toml"
    if platform == "darwin":
        return Path("/Library/Application Support/yardmaster/policy.toml")
    return Path("/etc/yardmaster/policy.toml")


def vscode_user_dirs(env: Mapping[str, str], platform: str) -> list[Path]:
    base = _user_config_base(env, platform)
    return [base / f / "User" for f in ("Code", "Code - Insiders") if (base / f / "User").is_dir()]
