from datetime import UTC, datetime

from yardmaster.model import Chat, Turn


def test_chat_and_turn_defaults():
    t = Turn(role="user", text="hi")
    assert (t.model, t.ts, t.tokens_in, t.tokens_out, t.tokens_cached) == (None, None, 0, 0, 0)
    now = datetime(2026, 11, 23, tzinfo=UTC)
    c = Chat("claude-code", "id1", "/w", "title", now, now, [t], 1, None, {"opus": 5.0}, [])
    assert c.credits is None and c.models["opus"] == 5.0 and c.turns == [t]
