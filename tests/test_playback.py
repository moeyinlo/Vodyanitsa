import pytest

from genshin_midi.mapping import MappedSpan
from genshin_midi.playback import PlaybackEngine, PlaybackState


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeSink:
    def __init__(self):
        self.events = []

    def key_down(self, key):
        self.events.append(("down", key))

    def key_up(self, key):
        self.events.append(("up", key))


class BatchSink(FakeSink):
    def __init__(self):
        super().__init__()
        self.batches = []

    def key_events(self, transitions):
        batch = tuple(transitions)
        self.batches.append(batch)
        for key, is_down in batch:
            self.events.append(("down" if is_down else "up", key))



def test_play_pause_resume_and_duration_release_keys():
    clock = FakeClock()
    sink = FakeSink()
    engine = PlaybackEngine(sink, clock=clock)
    engine.load([MappedSpan(0, 1, ("A",))], duration=2)

    engine.play()
    engine.tick()
    assert sink.events == [("down", "A")]

    clock.advance(0.4)
    engine.pause()
    assert engine.state is PlaybackState.PAUSED
    assert sink.events[-1] == ("up", "A")

    clock.advance(5)
    engine.play()
    engine.tick()
    assert sink.events[-1] == ("down", "A")

    clock.advance(0.61)
    engine.tick()
    assert sink.events[-1] == ("up", "A")
    assert abs(engine.position - 1.01) < 1e-9


def test_reset_releases_active_keys_and_returns_to_zero():
    clock = FakeClock()
    sink = FakeSink()
    engine = PlaybackEngine(sink, clock=clock)
    engine.load([MappedSpan(0, 3, ("Q", "W"))], duration=3)
    engine.play()
    engine.tick()
    clock.advance(0.2)

    engine.reset()

    assert engine.state is PlaybackState.STOPPED
    assert engine.position == 0
    assert sink.events[-2:] == [("up", "Q"), ("up", "W")]



def test_overlapping_spans_do_not_release_a_shared_key_early():
    clock = FakeClock()
    sink = FakeSink()
    engine = PlaybackEngine(sink, clock=clock)
    engine.load(
        [MappedSpan(0, 0.5, ("A",)), MappedSpan(0.25, 0.75, ("A",))],
        duration=1,
    )

    engine.play()
    engine.tick()
    clock.advance(0.25)
    engine.tick()
    clock.advance(0.25)
    engine.tick()

    assert sink.events == [("down", "A")]
    clock.advance(0.25)
    engine.tick()
    assert sink.events == [("down", "A"), ("up", "A")]


def test_simultaneous_chord_key_transitions_are_batched():
    clock = FakeClock()
    sink = BatchSink()
    engine = PlaybackEngine(sink, clock=clock)
    engine.load([MappedSpan(0, 0.5, ("Q", "W", "E"))], duration=1)

    engine.play()
    engine.tick()
    clock.advance(0.5)
    engine.tick()

    assert sink.batches == [
        (("E", True), ("Q", True), ("W", True)),
        (("E", False), ("Q", False), ("W", False)),
    ]


def test_batched_same_key_retrigger_releases_then_presses_at_shared_timestamp():
    clock = FakeClock()
    sink = BatchSink()
    engine = PlaybackEngine(sink, clock=clock)
    engine.load(
        [MappedSpan(0, 0.5, ("A",)), MappedSpan(0.5, 1, ("A",))],
        duration=1,
    )

    engine.play()
    engine.tick()
    clock.advance(0.5)
    engine.tick()

    assert sink.batches == [(("A", True),), (("A", False), ("A", True))]


def test_failed_batch_remains_pending_for_retry():
    class RetryBatchSink(BatchSink):
        def __init__(self):
            super().__init__()
            self.fail_once = True

        def key_events(self, transitions):
            if self.fail_once:
                self.fail_once = False
                raise OSError("simulated input failure")
            super().key_events(transitions)

    sink = RetryBatchSink()
    engine = PlaybackEngine(sink, clock=FakeClock())
    engine.load([MappedSpan(0, 0.5, ("A",))], duration=1)
    engine.play()

    with pytest.raises(OSError, match="simulated input failure"):
        engine.tick()

    engine.tick()

    assert sink.batches == [(("A", True),)]
    assert sink.events == [("down", "A")]



def test_reset_attempts_to_release_every_key_even_if_one_release_fails():
    class FailingSink(FakeSink):
        fail_q_release = True

        def key_up(self, key):
            self.events.append(("up-attempt", key))
            if key == "Q" and self.fail_q_release:
                raise OSError("simulated key release failure")
            self.events.append(("up", key))

    sink = FailingSink()
    engine = PlaybackEngine(sink, clock=FakeClock())
    engine.load([MappedSpan(0, 1, ("Q", "W"))], duration=1)
    engine.play()
    engine.tick()

    with pytest.raises(OSError):
        engine.reset()

    assert ("up-attempt", "Q") in sink.events
    assert ("up", "W") in sink.events
    assert engine.state is PlaybackState.STOPPED
    with pytest.raises(RuntimeError, match="reset"):
        engine.play()

    sink.fail_q_release = False
    engine.reset()
    engine.play()
    assert engine.state is PlaybackState.PLAYING
