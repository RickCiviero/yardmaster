"""The usage ledger counts tokens and Copilot credits, sorts them by strength, and never turns them into money."""

from pathlib import Path

import pytest
from chats import chat, turn
from yardmaster.catalog import load_catalog
from yardmaster.ledger import ledger, render_ledger

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "scripts" / "yardmaster" / "models.json")


def test_copilot_credits_are_reported_as_they_are_with_their_tier():
    c = chat("v1", harness="vscode-copilot", credits=2.5, models={"opus": 2.0, "sonnet": 0.5})
    r = ledger([c], CATALOG)["harnesses"]["vscode-copilot"]
    assert r["credits"] == pytest.approx(2.5)
    assert r["models"]["opus"]["credits"] == pytest.approx(2.0) and r["models"]["opus"]["tier"] == "heavy"
    assert r["models"]["sonnet"]["tier"] == "standard"


def test_fresh_tokens_are_input_plus_output_and_cache_reads_are_shown_apart():
    c = chat("c1", [turn("user", "hi"), turn("assistant", "ok", "opus", tin=1000, tout=500, tcache=20000)])
    rep = ledger([c], CATALOG)
    assert rep["fresh_tokens"] == 1500
    assert rep["harnesses"]["claude-code"]["tokens_cached"] == 20000
    assert rep["by_tier"]["heavy"] == 1500


def test_a_model_outside_the_catalog_is_listed_as_unknown_strength():
    c = chat("c1", [turn("assistant", "ok", "mystery-9", tin=10, tout=5)])
    rep = ledger([c], CATALOG)
    assert rep["by_tier"]["unknown"] == 15
    assert "not in the catalog" in render_ledger(rep)


def test_the_report_never_shows_money():
    c = chat("c1", [turn("assistant", "ok", "opus", tin=1_000_000, tout=1_000_000)])
    text = render_ledger(ledger([c], CATALOG))
    assert "$" not in text and "USD" not in text and "Fresh tokens (input + output): 2,000,000" in text


def test_empty_range_says_so():
    rep = ledger([], CATALOG)
    assert rep["harnesses"] == {} and rep["fresh_tokens"] == 0 and "no chats" in render_ledger(rep).lower()


def test_the_report_never_contains_chat_text():
    c = chat("c1", [turn("user", "SECRET-PHRASE-42"), turn("assistant", "SECRET-REPLY-99", "opus", tin=3, tout=4)])
    text = render_ledger(ledger([c], CATALOG))
    assert "SECRET-PHRASE-42" not in text and "SECRET-REPLY-99" not in text
