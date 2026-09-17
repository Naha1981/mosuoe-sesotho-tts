from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .services import engine


@dataclass
class CallSession:
    call_id: str
    caller: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    history: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_turn(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text})
        self.history = self.history[-20:]

    def process_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return "Ke kopa o phete seo hape."
        self.add_turn("user", text)
        reply = engine.respond(text, self.history[:-1])
        self.add_turn("model", reply)
        return reply


class CallManager:
    def __init__(self) -> None:
        self.sessions: dict[str, CallSession] = {}

    def create(self, call_id: str, caller: str | None = None) -> CallSession:
        session = CallSession(call_id=call_id, caller=caller)
        self.sessions[call_id] = session
        return session

    def get(self, call_id: str) -> CallSession | None:
        return self.sessions.get(call_id)

    def remove(self, call_id: str) -> None:
        self.sessions.pop(call_id, None)


calls = CallManager()
