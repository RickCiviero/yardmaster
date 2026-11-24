import socket

import pytest


def test_version_and_help(capsys):
    from yardmaster import __version__
    from yardmaster.cli import main

    assert __version__ == "1.1.1"
    assert main(["--version"]) == 0
    assert "1.1.1" in capsys.readouterr().out


def test_no_network_guard_active():
    with pytest.raises(AssertionError, match="network used"):
        socket.create_connection(("example.com", 80))
