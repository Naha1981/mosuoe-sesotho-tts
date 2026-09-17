from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .call import calls


@dataclass
class CallEvent:
    """Provider-neutral representation of a telephony event."""

    event_type: str
    call_id: str
    caller: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TelephonyGateway:
    """Keeps telephony providers separate from the conversation engine."""

    def start(self, event: CallEvent) -> dict[str, Any]:
        session = calls.create(event.call_id, event.caller)
        session.metadata.update(event.metadata)
        session.metadata["provider"] = event.metadata.get("provider", "unknown")
        session.metadata["started_at"] = datetime.now(timezone.utc).isoformat()

        greeting = "Lumela. Ke mothusi wa Lesotho. Nka o thusa ka eng kajeno?"
        session.add_turn("model", greeting)
        return {
            "call_id": event.call_id,
            "action": "speak",
            "text": greeting,
        }

    def receive_text(self, event: CallEvent) -> dict[str, Any]:
        session = calls.get(event.call_id)
        if session is None:
            raise KeyError(event.call_id)
        if not event.text:
            return {"call_id": event.call_id, "action": "listen"}

        response = session.process_text(event.text)
        return {
            "call_id": event.call_id,
            "action": "speak",
            "text": response,
        }

    def end(self, call_id: str) -> dict[str, Any]:
        calls.remove(call_id)
        return {"call_id": call_id, "action": "hangup"}


gateway = TelephonyGateway()
