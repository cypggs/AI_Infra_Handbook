from multimodal_inference_mini.duplex import (
    DuplexSession,
    Event,
    State,
    run_trace,
)


class TestTransitions:
    def test_normal_turn_lifecycle(self):
        s = run_trace([
            (0, Event.USER_SPEECH_START),
            (1000, Event.USER_SPEECH_END),
            (1250, Event.RESPONSE_READY),
            (5000, Event.RESPONSE_DONE),
        ])
        assert s.state is State.LISTENING
        assert s.turns_completed == 1
        assert s.interruptions == 0

    def test_barge_in_confirmed(self):
        s = run_trace([
            (0, Event.USER_SPEECH_END),
            (250, Event.RESPONSE_READY),
            (1000, Event.USER_SPEECH_START),
            (1100, Event.SPEECH_CONFIRMED),
        ])
        assert s.state is State.LISTENING
        assert s.interruptions == 1

    def test_false_alarm_resumes_speaking(self):
        s = run_trace([
            (0, Event.USER_SPEECH_END),
            (250, Event.RESPONSE_READY),
            (1000, Event.USER_SPEECH_START),
            (1300, Event.SPEECH_FALSE_ALARM),
        ])
        assert s.state is State.SPEAKING
        assert s.false_alarms == 1
        assert s.interruptions == 1

    def test_history_truncation_tracks_playback(self):
        s = DuplexSession()
        s.step(0, Event.USER_SPEECH_END)
        s.step(250, Event.RESPONSE_READY, duration_ms=3000)
        s.advance_playback(900, 500)
        s.step(1000, Event.USER_SPEECH_START)
        s.step(1100, Event.SPEECH_CONFIRMED)
        assert s.heard_ms() == 500
        note = [t for t in s.transitions if t.event is Event.SPEECH_CONFIRMED][0]
        assert "500" in note.note

    def test_response_done_requires_speaking(self):
        s = DuplexSession()
        s.step(0, Event.RESPONSE_DONE)  # ignored while LISTENING
        assert s.state is State.LISTENING
        assert s.turns_completed == 0

    def test_speech_start_in_listening_is_noop(self):
        s = DuplexSession()
        s.step(0, Event.USER_SPEECH_START)
        assert s.state is State.LISTENING
        assert s.transitions == []

    def test_response_ready_requires_processing(self):
        s = DuplexSession()
        s.step(0, Event.RESPONSE_READY)
        assert s.state is State.LISTENING

    def test_trace_is_deterministic(self):
        events = [
            (0, Event.USER_SPEECH_END),
            (250, Event.RESPONSE_READY),
            (1000, Event.USER_SPEECH_START),
            (1300, Event.SPEECH_FALSE_ALARM),
            (2000, Event.RESPONSE_DONE),
        ]
        a, b = run_trace(events), run_trace(events)
        assert [(t.at_ms, t.event, t.from_state, t.to_state) for t in a.transitions] == [
            (t.at_ms, t.event, t.from_state, t.to_state) for t in b.transitions
        ]

    def test_full_conversation(self):
        s = DuplexSession()
        s.step(0, Event.USER_SPEECH_START)
        s.step(1200, Event.USER_SPEECH_END)
        s.step(1450, Event.RESPONSE_READY, duration_ms=4000)
        s.advance_playback(2000, 400)
        s.step(2100, Event.USER_SPEECH_START)
        s.step(2200, Event.SPEECH_CONFIRMED)
        s.step(3400, Event.USER_SPEECH_END)
        s.step(3650, Event.RESPONSE_READY, duration_ms=2500)
        s.advance_playback(4200, 500)
        s.step(4300, Event.USER_SPEECH_START)
        s.step(4450, Event.SPEECH_FALSE_ALARM)
        s.step(7000, Event.RESPONSE_DONE)
        assert s.state is State.LISTENING
        assert s.turns_completed == 1
        assert s.interruptions == 2
        assert s.false_alarms == 1

    def test_advance_playback_ignored_outside_speaking(self):
        s = DuplexSession()
        s.advance_playback(100, 999)
        assert s.response_played_ms == 0

    def test_heard_never_exceeds_total(self):
        s = DuplexSession()
        s.step(0, Event.USER_SPEECH_END)
        s.step(250, Event.RESPONSE_READY, duration_ms=1000)
        s.advance_playback(500, 5000)
        assert s.heard_ms() == 1000
