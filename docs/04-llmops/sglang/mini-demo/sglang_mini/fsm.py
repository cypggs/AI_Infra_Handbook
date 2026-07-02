"""A tiny regex-to-FSM compiler for teaching structured generation.

Real SGLang integrates with xgrammar / outlines for full JSON-schema/EBNF
support. This module implements a small subset of regular expressions using
Thompson's construction so the demo can show the core idea: at each decode
step, only tokens that keep the FSM on a path to acceptance are allowed.

Supported syntax:
- literals: A, b, 1, etc.
- char class: \\d (digits 0-9)
- grouping: (expr)
- alternation: A|B
- repetition: A+, A*, A?
- exact repetition: A{3}
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, List, Optional, Set, Tuple


class _AnyDigit:
    """Transition label that matches any digit symbol."""
    def __contains__(self, symbol: int) -> bool:
        return 48 <= symbol <= 57  # '0'..'9'


ANY_DIGIT = _AnyDigit()


@dataclass
class State:
    """One state in an NFA."""
    tid: int
    # symbol -> list of target states. symbol can be an int or ANY_DIGIT.
    transitions: Dict[object, List["State"]] = field(default_factory=lambda: {})
    epsilon: List["State"] = field(default_factory=list)
    is_accept: bool = False

    def add_transition(self, symbol: object, target: "State") -> None:
        self.transitions.setdefault(symbol, []).append(target)

    def __hash__(self) -> int:
        return self.tid

    def __eq__(self, other: object) -> bool:
        return isinstance(other, State) and self.tid == other.tid


@dataclass
class Fragment:
    """A partial NFA with one start state and one accept state."""
    start: State
    accept: State


class RegexFSM:
    """Finite-state machine compiled from a regex-like pattern."""

    def __init__(self, pattern: str):
        self.pattern = pattern
        self._state_counter = 0
        self.start_state, self.accept_state = self._compile(pattern)
        self._accept_reachable: Set[int] = self._compute_accept_reachable()

    def _new_state(self) -> State:
        self._state_counter += 1
        return State(tid=self._state_counter)

    # ------------------------------------------------------------------
    # Parser / Thompson construction
    # ------------------------------------------------------------------
    def _compile(self, pattern: str) -> Tuple[State, State]:
        self._tokens = list(pattern)
        self._pos = 0
        fragment = self._parse_regex()
        fragment.accept.is_accept = True
        return fragment.start, fragment.accept

    def _peek(self) -> Optional[str]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> Optional[str]:
        ch = self._peek()
        self._pos += 1
        return ch

    def _parse_regex(self) -> Fragment:
        """regex = term ('|' term)*"""
        frag = self._parse_term()
        while self._peek() == "|":
            self._consume()  # '|'
            right = self._parse_term()
            start = self._new_state()
            accept = self._new_state()
            start.epsilon.extend([frag.start, right.start])
            frag.accept.epsilon.append(accept)
            right.accept.epsilon.append(accept)
            frag = Fragment(start, accept)
        return frag

    def _parse_term(self) -> Fragment:
        """term = factor*"""
        fragments: List[Fragment] = []
        while self._peek() is not None and self._peek() not in "|)":
            fragments.append(self._parse_factor())
        if not fragments:
            # Empty term matches empty string.
            s = self._new_state()
            a = self._new_state()
            s.epsilon.append(a)
            return Fragment(s, a)
        result = fragments[0]
        for frag in fragments[1:]:
            result.accept.epsilon.append(frag.start)
            result = Fragment(result.start, frag.accept)
        return result

    def _parse_factor(self) -> Fragment:
        """factor = atom ('+'|'?'|'*'|'{n}')?"""
        frag = self._parse_atom()
        while True:
            op = self._peek()
            if op == "+":
                self._consume()
                # one or more: concat atom with star of atom
                star = self._star(frag)
                frag.accept.epsilon.append(star.start)
                frag = Fragment(frag.start, star.accept)
            elif op == "*":
                self._consume()
                frag = self._star(frag)
            elif op == "?":
                self._consume()
                start = self._new_state()
                accept = self._new_state()
                start.epsilon.extend([frag.start, accept])
                frag.accept.epsilon.append(accept)
                frag = Fragment(start, accept)
            elif op == "{":
                self._consume()  # '{'
                count = self._parse_number()
                if self._peek() != "}":
                    raise ValueError("Expected '}' in repetition")
                self._consume()  # '}'
                frag = self._repeat_exact(frag, count)
            else:
                break
        return frag

    def _parse_number(self) -> int:
        num = ""
        while self._peek() is not None and self._peek().isdigit():
            num += self._consume()  # type: ignore
        if not num:
            raise ValueError("Expected number in repetition")
        return int(num)

    def _parse_atom(self) -> Fragment:
        ch = self._peek()
        if ch == "(":
            self._consume()  # '('
            frag = self._parse_regex()
            if self._peek() != ")":
                raise ValueError("Expected ')'")
            self._consume()  # ')'
            return frag
        if ch == "\\":
            self._consume()  # '\'
            next_ch = self._consume()
            if next_ch == "d":
                return self._char_class(ANY_DIGIT)
            raise ValueError(f"Unknown escape: \\{next_ch}")
        if ch is None or ch in "|)+*?{":
            raise ValueError(f"Unexpected character: {ch}")
        self._consume()
        return self._literal(ord(ch))

    def _literal(self, symbol: int) -> Fragment:
        start = self._new_state()
        accept = self._new_state()
        start.add_transition(symbol, accept)
        return Fragment(start, accept)

    def _char_class(self, predicate: Callable[[int], bool]) -> Fragment:
        start = self._new_state()
        accept = self._new_state()
        start.add_transition(predicate, accept)
        return Fragment(start, accept)

    def _star(self, frag: Fragment) -> Fragment:
        start = self._new_state()
        accept = self._new_state()
        start.epsilon.extend([frag.start, accept])
        frag.accept.epsilon.extend([frag.start, accept])
        return Fragment(start, accept)

    def _repeat_exact(self, frag: Fragment, count: int) -> Fragment:
        if count == 0:
            s = self._new_state()
            a = self._new_state()
            s.epsilon.append(a)
            return Fragment(s, a)
        result = frag
        for _ in range(count - 1):
            copy = self._copy_fragment(frag)
            result.accept.epsilon.append(copy.start)
            result = Fragment(result.start, copy.accept)
        return result

    def _copy_fragment(self, frag: Fragment) -> Fragment:
        """Return a deep copy of a fragment (used for exact repetition)."""
        old_by_tid: Dict[int, State] = {}
        new_by_tid: Dict[int, State] = {}

        # First pass: discover all original states and create new counterparts.
        queue = deque([frag.start])
        while queue:
            s = queue.popleft()
            if s.tid in old_by_tid:
                continue
            old_by_tid[s.tid] = s
            new = self._new_state()
            new.is_accept = s.is_accept
            new_by_tid[s.tid] = new
            for targets in s.transitions.values():
                for t in targets:
                    queue.append(t)
            for t in s.epsilon:
                queue.append(t)

        # Second pass: copy transitions using the old->new mapping.
        for old_tid, old_state in old_by_tid.items():
            new_state = new_by_tid[old_tid]
            for symbol, targets in old_state.transitions.items():
                for t in targets:
                    new_state.add_transition(symbol, new_by_tid[t.tid])
            for t in old_state.epsilon:
                new_state.epsilon.append(new_by_tid[t.tid])

        return Fragment(new_by_tid[frag.start.tid], new_by_tid[frag.accept.tid])

    def _state_by_tid(self, start: State, tid: int) -> State:
        queue = deque([start])
        seen = set()
        while queue:
            s = queue.popleft()
            if s.tid in seen:
                continue
            seen.add(s.tid)
            if s.tid == tid:
                return s
            for targets in s.transitions.values():
                for t in targets:
                    queue.append(t)
            for t in s.epsilon:
                queue.append(t)
        raise KeyError(f"State {tid} not found")

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------
    def _epsilon_closure(self, states: FrozenSet[State]) -> FrozenSet[State]:
        closure: Set[State] = set(states)
        queue = deque(states)
        while queue:
            s = queue.popleft()
            for t in s.epsilon:
                if t not in closure:
                    closure.add(t)
                    queue.append(t)
        return frozenset(closure)

    def _step(self, states: FrozenSet[State], symbol: int) -> FrozenSet[State]:
        next_states: Set[State] = set()
        for s in states:
            for trans_symbol, targets in s.transitions.items():
                if trans_symbol is ANY_DIGIT:
                    if symbol in ANY_DIGIT:
                        next_states.update(targets)
                elif trans_symbol == symbol:
                    next_states.update(targets)
        return self._epsilon_closure(frozenset(next_states))

    def _compute_accept_reachable(self) -> Set[int]:
        """Return set of state ids from which an accept state is reachable."""
        # Reverse graph over epsilon and symbol transitions.
        reverse: Dict[int, Set[int]] = {i: set() for i in range(1, self._state_counter + 1)}
        # Need to iterate all states.
        all_states = self._collect_states()
        for s in all_states:
            for targets in s.transitions.values():
                for t in targets:
                    reverse[t.tid].add(s.tid)
            for t in s.epsilon:
                reverse[t.tid].add(s.tid)

        reachable: Set[int] = set()
        queue = deque([s.tid for s in all_states if s.is_accept])
        for tid in queue:
            reachable.add(tid)
        while queue:
            tid = queue.popleft()
            for pred in reverse[tid]:
                if pred not in reachable:
                    reachable.add(pred)
                    queue.append(pred)
        return reachable

    def _collect_states(self) -> Set[State]:
        states: Set[State] = set()
        queue = deque([self.start_state])
        while queue:
            s = queue.popleft()
            if s in states:
                continue
            states.add(s)
            for targets in s.transitions.values():
                for t in targets:
                    queue.append(t)
            for t in s.epsilon:
                queue.append(t)
        return states

    # ------------------------------------------------------------------
    # Public API used by the sampler
    # ------------------------------------------------------------------
    def initial_states(self) -> FrozenSet[State]:
        return self._epsilon_closure(frozenset([self.start_state]))

    def step(self, states: FrozenSet[State], symbol: int) -> FrozenSet[State]:
        return self._step(states, symbol)

    def allowed_tokens(self, states: FrozenSet[State], vocab: List[int]) -> List[int]:
        """Return tokens that keep the FSM on a path to acceptance."""
        allowed: List[int] = []
        for token in vocab:
            next_states = self._step(states, token)
            if not next_states:
                continue
            if any(s.tid in self._accept_reachable for s in next_states):
                allowed.append(token)
        return allowed

    def is_accepting(self, states: FrozenSet[State]) -> bool:
        return any(s.is_accept for s in states)

    def can_finish(self, states: FrozenSet[State]) -> bool:
        """True if the current state set can still reach an accept state."""
        return any(s.tid in self._accept_reachable for s in states)
