"""Session state machine for the agent runtime."""

from enum import Enum, auto


class State(Enum):
    """Runtime states."""

    IDLE = auto()
    PLANNING = auto()
    ACTING = auto()
    OBSERVING = auto()
    DONE = auto()
    ERROR = auto()


class SessionState:
    """Simple state machine with transition validation."""

    _valid = {
        State.IDLE: {State.PLANNING, State.ERROR},
        State.PLANNING: {State.ACTING, State.ERROR},
        State.ACTING: {State.OBSERVING, State.DONE, State.ERROR},
        State.OBSERVING: {State.ACTING, State.ERROR},
        State.DONE: set(),
        State.ERROR: set(),
    }

    def __init__(self, initial: State = State.IDLE):
        self._state = initial

    @property
    def state(self) -> State:
        return self._state

    def transition(self, target: State) -> None:
        if target not in self._valid[self._state]:
            raise RuntimeError(
                f"Invalid state transition from {self._state.name} to {target.name}"
            )
        self._state = target

    def is_terminal(self) -> bool:
        return self._state in {State.DONE, State.ERROR}

    def __repr__(self) -> str:  # pragma: no cover
        return f"SessionState({self._state.name})"
