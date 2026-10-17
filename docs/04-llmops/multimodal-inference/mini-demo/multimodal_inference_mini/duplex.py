"""Full-duplex conversation state machine.

A realtime voice agent must behave like a human on a phone call: listen while
the other side may speak, yield promptly when interrupted, and recover from
false alarms (coughs, backchannel "嗯嗯", background noise).

States:
- LISTENING:  waiting for / receiving user speech
- PROCESSING: user finished a turn, response is being generated
- SPEAKING:   response audio is playing out
- INTERRUPTED: user speech was detected during SPEAKING; confirmation pending

Events (fed in timestamp order):
- USER_SPEECH_START / USER_SPEECH_END
- SPEECH_CONFIRMED (VAD trigger turned out to carry real words)
- SPEECH_FALSE_ALARM (VAD fired but no words followed -> resume)
- RESPONSE_READY / RESPONSE_DONE

Deterministic: identical event traces always produce identical transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class State(Enum):
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


class Event(Enum):
    USER_SPEECH_START = "USER_SPEECH_START"
    USER_SPEECH_END = "USER_SPEECH_END"
    SPEECH_CONFIRMED = "SPEECH_CONFIRMED"
    SPEECH_FALSE_ALARM = "SPEECH_FALSE_ALARM"
    RESPONSE_READY = "RESPONSE_READY"
    RESPONSE_DONE = "RESPONSE_DONE"


@dataclass(frozen=True)
class Transition:
    at_ms: int
    event: Event
    from_state: State
    to_state: State
    note: str = ""


@dataclass
class DuplexSession:
    """One conversation with a deterministic duplex controller."""

    false_alarm_grace_ms: int = 0  # reserved for future timing logic
    state: State = field(default=State.LISTENING, init=False)
    transitions: list = field(default_factory=list, init=False)

    # bookkeeping for history truncation on interruption
    response_total_ms: int = field(default=0, init=False)
    response_played_ms: int = field(default=0, init=False)
    interruptions: int = field(default=0, init=False)
    false_alarms: int = field(default=0, init=False)
    turns_completed: int = field(default=0, init=False)

    # ------------------------------------------------------------------
    def _go(self, at_ms: int, event: Event, to: State, note: str = "") -> None:
        self.transitions.append(
            Transition(at_ms, event, self.state, to, note)
        )
        self.state = to

    def step(self, at_ms: int, event: Event, **kw) -> State:
        """Apply one event. Unknown/invalid combinations are ignored."""
        s = self.state

        if event is Event.USER_SPEECH_START:
            if s is State.SPEAKING:
                self.interruptions += 1
                self._go(at_ms, event, State.INTERRUPTED,
                         f"playback at {self.response_played_ms}/"
                         f"{self.response_total_ms} ms")
            # In LISTENING/PROCESSING, speech start is expected; stay put.

        elif event is Event.SPEECH_CONFIRMED:
            if s is State.INTERRUPTED:
                # Real barge-in: freeze what the user actually heard.
                heard = min(self.response_played_ms, self.response_total_ms)
                self._go(at_ms, event, State.LISTENING,
                         f"history truncated to {heard} ms of playback")

        elif event is Event.SPEECH_FALSE_ALARM:
            if s is State.INTERRUPTED:
                self.false_alarms += 1
                self._go(at_ms, event, State.SPEAKING, "resume playback")

        elif event is Event.USER_SPEECH_END:
            if s is State.LISTENING:
                self._go(at_ms, event, State.PROCESSING, "turn closed")
            # INTERRUPTED + USER_SPEECH_END is handled by CONFIRMED/FALSE_ALARM.

        elif event is Event.RESPONSE_READY:
            if s is State.PROCESSING:
                self.response_total_ms = int(kw.get("duration_ms", 0))
                self.response_played_ms = 0
                self._go(at_ms, event, State.SPEAKING, "playback started")

        elif event is Event.RESPONSE_DONE:
            if s is State.SPEAKING:
                self.turns_completed += 1
                self._go(at_ms, event, State.LISTENING, "turn completed")

        return self.state

    def advance_playback(self, at_ms: int, played_ms: int) -> None:
        """Update playback position while SPEAKING (drives truncation math)."""
        if self.state is State.SPEAKING:
            self.response_played_ms = max(self.response_played_ms, played_ms)

    def heard_ms(self) -> int:
        """How much of the current response the user has actually heard."""
        return min(self.response_played_ms, self.response_total_ms)


def run_trace(events: list[tuple[int, Event]], **kw) -> DuplexSession:
    """Convenience: build a session and replay a trace of (ms, event)."""
    session = DuplexSession(**kw)
    for at_ms, event in events:
        session.step(at_ms, event)
    return session
