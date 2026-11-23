import importlib.util
from pathlib import Path

import pytest
from synthetic import SINCE, UNTIL, copilot_home
from yardmaster.collectors import COLLECTORS, CollectorContext
from yardmaster.collectors.copilot_cli import collect

REF = Path(__file__).resolve().parents[2] / "reference" / "copilot_chats_to_md.py"


@pytest.fixture
def chome(tmp_path):
    return copilot_home(tmp_path)


def _ctx(home, **kw):
    return CollectorContext(since=SINCE, until=UNTIL, env={}, platform="linux", roots=[home], **kw)


def _by_id(chats):
    return {c.chat_id: c for c in chats}


def test_registered():
    assert COLLECTORS["copilot-cli"] is collect


def test_parity_with_reference(chome):
    spec = importlib.util.spec_from_file_location("ym_reference2", REF)
    ref = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref)
    want = {c["id"]: c for c in ref.collect_cli(chome, SINCE, UNTIL, False)}
    got = _by_id(collect(_ctx(chome)))
    assert got.keys() == want.keys() == {"cliOk", "cliLate", "cliNoShutdown", "cliPartial", "bare"}
    for cid, w in want.items():
        g = got[cid]
        assert g.requests == w["requests"] and g.credits == pytest.approx(w["credits"])
        assert "; ".join(g.notes) == w["note"] and g.workspace == w["workspace"] and g.title == w["title"]
        assert list(g.models) == list(w["models"]) and g.first == w["first"] and g.last == w["last"]


def test_credits_from_last_shutdown_in_range(chome):
    c = _by_id(collect(_ctx(chome)))
    assert c["cliOk"].credits == pytest.approx(2.5) and c["cliOk"].requests == 2
    assert c["bare"].credits == pytest.approx(3.0)
    assert c["cliOk"].harness == "copilot-cli" and c["cliOk"].workspace == "C:\ws\app"


def test_notes_verbatim(chome):
    c = _by_id(collect(_ctx(chome)))
    assert c["cliNoShutdown"].notes == ["no shutdown snapshot (credits unknown)"] and c["cliNoShutdown"].credits == 0.0
    assert c["cliPartial"].notes == ["aiCreditsStatus=partial"]
    late = c["cliLate"]
    assert late.credits == 0.0 and late.notes[0].startswith("session ended ")
    assert late.notes[0].endswith("outside range: credits not counted here")


def test_models_and_turns(chome):
    p = _by_id(collect(_ctx(chome)))["cliPartial"]
    assert p.models == {"gpt-5": 0.0, "o4": 0.0}
    assert [t.role for t in p.turns] == ["user", "assistant"] and p.turns[0].text == "cli question 0"
    assert p.turns[1].model == "gpt-5"


def test_stale_and_outside_range_skipped(chome):
    assert {"cliStale", "cliOutside"}.isdisjoint(_by_id(collect(_ctx(chome))))


def test_project_filter_uses_cwd(chome):
    got = {c.chat_id for c in collect(_ctx(chome, project=Path("C:\ws\other")))}
    assert got == {"cliLate"}


def test_home_from_env(tmp_path, chome):
    ctx = CollectorContext(since=SINCE, until=UNTIL, env={"COPILOT_HOME": str(chome)}, platform="linux")
    assert "cliOk" in _by_id(collect(ctx))
    ctx = CollectorContext(since=SINCE, until=UNTIL, env={"HOME": str(tmp_path)}, platform="linux")
    assert "cliOk" in _by_id(collect(ctx))  # default ~/.copilot


def test_empty_or_missing_home(tmp_path):
    assert collect(_ctx(tmp_path / "nope")) == []


def test_nan_and_negative_nano_ignored(tmp_path):
    from synthetic import iso, jsonl

    ev = [{"type": "user.message", "timestamp": iso(2026, 9, 10), "data": {"content": "q"}},
          {"type": "session.shutdown", "timestamp": iso(2026, 9, 10, 12),
           "data": {"accountingSnapshot": {"totalNanoAiu": float("nan")}}}]
    jsonl(tmp_path / "session-state" / "x" / "events.jsonl", ev)
    (c,) = collect(_ctx(tmp_path))
    assert c.credits == 0.0 and c.notes == ["no shutdown snapshot (credits unknown)"]
