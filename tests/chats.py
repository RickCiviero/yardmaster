"""Tiny builders for normalised Chat objects in unit tests."""

from datetime import UTC, datetime

from yardmaster.model import Chat, Turn

T0 = datetime(2026, 9, 10, 10, 0, tzinfo=UTC)


def turn(role, text, model=None, tin=0, tout=0, tcache=0):
    return Turn(role, text, model=model, ts=T0, tokens_in=tin, tokens_out=tout, tokens_cached=tcache)


def chat(chat_id="c1", turns=None, harness="claude-code", workspace="/w", title="t", credits=None, models=None,
         requests=1, first=T0):
    turns = turns if turns is not None else [turn("user", "hello"), turn("assistant", "hi there", "opus", 10, 5)]
    return Chat(harness, chat_id, workspace, title, first, first, turns, requests, credits, models or {}, [])
