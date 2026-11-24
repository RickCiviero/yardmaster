from pathlib import Path

import pytest
from chats import chat, turn
from yardmaster.ledger import ledger, render_ledger
from yardmaster.pricing import load_pricing

PRICING = load_pricing(Path(__file__).resolve().parents[2] / "skills" / "yardmaster" / "pricing.json")


def test_copilot_spend_is_credits_times_a_cent():
    c = chat(harness="vscode-copilot", credits=2.5, models={"opus": 2.0, "gpt-5": 0.5}, requests=3)
    r = ledger([c], PRICING)["harnesses"]["vscode-copilot"]
    assert r["chats"] == 1 and r["requests"] == 3 and r["credits"] == pytest.approx(2.5)
    assert r["est_usd"] == pytest.approx(0.025) and r["models"]["opus"]["credits"] == pytest.approx(2.0)


def test_token_harness_priced_per_model_with_cache():
    c = chat(turns=[turn("assistant", "x", "claude-opus-5-5", 1_000_000, 1_000_000, 1_000_000), turn("user", "q")])
    r = ledger([c], PRICING)["harnesses"]["claude-code"]
    opus = PRICING.get("claude-code", "opus")
    assert r["est_usd"] == pytest.approx(opus.input + opus.output + opus.cached)
    assert r["tokens_in"] == 1_000_000 and r["tokens_out"] == 1_000_000 and r["tokens_cached"] == 1_000_000
    assert r["models"]["opus"]["tokens_out"] == 1_000_000  # reported under the canonical id


def test_unknown_model_is_listed_not_priced():
    c = chat(turns=[turn("assistant", "x", "mystery-9", 100, 100)])
    r = ledger([c], PRICING)
    assert r["harnesses"]["claude-code"]["est_usd"] == 0 and r["unpriced_models"] == ["claude-code:mystery-9"]


def test_total_and_render_has_no_chat_text():
    chats = [chat("a", harness="vscode-copilot", credits=100.0, models={"opus": 100.0}),
             chat("b", [turn("user", "SECRET PROMPT TEXT"), turn("assistant", "x", "sonnet", 1_000_000, 0)])]
    rep = ledger(chats, PRICING)
    assert rep["total_est_usd"] == pytest.approx(1.0 + 3.0)
    md = render_ledger(rep)
    assert "SECRET PROMPT TEXT" not in md and "vscode-copilot" in md and "claude-code" in md and "$4.00" in md


def test_empty_ledger():
    rep = ledger([], PRICING)
    assert rep["harnesses"] == {} and rep["total_est_usd"] == 0 and "no chats" in render_ledger(rep).lower()
