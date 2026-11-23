from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class Turn:
    role: Literal["user", "assistant", "tool"]
    text: str
    model: str | None = None
    ts: datetime | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0


@dataclass
class Chat:
    harness: str
    chat_id: str
    workspace: str
    title: str
    first: datetime
    last: datetime
    turns: list[Turn]
    requests: int
    credits: float | None  # Copilot credits; None for token-billed harnesses
    models: dict[str, float]  # model id -> credits (Copilot) or output tokens (others)
    notes: list[str]
