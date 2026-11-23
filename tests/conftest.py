import socket
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    for k, sub in {
        "HOME": "",
        "USERPROFILE": "",
        "APPDATA": "AppData/Roaming",
        "LOCALAPPDATA": "AppData/Local",
        "XDG_CONFIG_HOME": ".config",
        "XDG_STATE_HOME": ".local/state",
        "XDG_DATA_HOME": ".local/share",
    }.items():
        p = h / sub if sub else h
        p.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(k, str(p))
    return h


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
