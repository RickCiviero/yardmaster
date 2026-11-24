import pytest
from yardmaster.settings import Settings, load_settings


def _w(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_defaults_when_no_files(tmp_path):
    s = load_settings({}, "linux", policy=tmp_path / "none.toml", config=tmp_path / "none2.toml")
    assert s == Settings(frozenset(), None, False, 40, s.sources)
    assert set(s.sources.values()) == {"default"}


def test_user_config_applies(tmp_path):
    cfg = _w(tmp_path, "c.toml", 'deny_models = ["opus"]\nharnesses = ["codex"]\nredact_pii = true\nmax_batches = 7\n')
    s = load_settings({}, "linux", policy=tmp_path / "none.toml", config=cfg)
    assert s.deny_models == {"opus"} and s.harnesses == {"codex"} and s.redact_pii and s.max_batches == 7
    assert s.sources["deny_models"] == "config"


def test_policy_user_cannot_widen(tmp_path):
    pol = _w(tmp_path, "p.toml", 'deny_models = ["opus"]\nharnesses = ["claude-code"]\nredact_pii = true\nmax_batches = 10\n')
    cfg = _w(tmp_path, "c.toml", 'deny_models = []\nharnesses = ["claude-code", "codex"]\nredact_pii = false\nmax_batches = 1000\n')
    s = load_settings({}, "linux", policy=pol, config=cfg)
    assert s.deny_models == {"opus"}  # an empty user list cannot remove the admin deny
    assert s.harnesses == {"claude-code"}  # intersection, never the union
    assert s.redact_pii is True and s.max_batches == 10


def test_user_can_narrow_further(tmp_path):
    pol = _w(tmp_path, "p.toml", 'deny_models = ["opus"]\nharnesses = ["claude-code", "codex"]\n')
    cfg = _w(tmp_path, "c.toml", 'deny_models = ["haiku"]\nharnesses = ["codex"]\nmax_batches = 5\n')
    s = load_settings({}, "linux", policy=pol, config=cfg)
    assert s.deny_models == {"opus", "haiku"} and s.harnesses == {"codex"} and s.max_batches == 5


def test_settings_sources_reported(tmp_path):
    pol = _w(tmp_path, "p.toml", 'deny_models = ["opus"]\nmax_batches = 10\n')
    cfg = _w(tmp_path, "c.toml", 'deny_models = ["haiku"]\nredact_pii = true\n')
    s = load_settings({}, "linux", policy=pol, config=cfg)
    assert s.sources == {"deny_models": "policy+config", "harnesses": "default", "redact_pii": "config", "max_batches": "policy"}


@pytest.mark.parametrize(
    "text",
    ["deny_models = 'opus'", "harnesses = [1]", "redact_pii = 'yes'", "max_batches = 0", "max_batches = true",
     "not toml [", "deny_models = [\"a\", 3]"],
)
def test_invalid_values_fail_closed(tmp_path, text):
    for kind in ("policy", "config"):
        bad = _w(tmp_path, f"{kind}.toml", text)
        kw = {"policy": tmp_path / "none", "config": tmp_path / "none"} | {kind: bad}
        with pytest.raises(ValueError, match=kind if kind == "policy" else "config"):
            load_settings({}, "linux", **kw)


def test_unknown_keys_rejected(tmp_path):
    with pytest.raises(ValueError):
        load_settings({}, "linux", policy=tmp_path / "none", config=_w(tmp_path, "c.toml", "allow_everything = true"))


def test_default_paths_come_from_platform_dirs(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path), "HOME": str(tmp_path)}
    (tmp_path / "yardmaster").mkdir()
    (tmp_path / "yardmaster" / "config.toml").write_text("redact_pii = true\n")
    assert load_settings(env, "linux").redact_pii is True
