from __future__ import annotations

from enum import Enum
from time import monotonic
from typing import Callable, Protocol

from .mapping import MappedSpan


class KeySink(Protocol):
    def key_down(self, key: str) -> None: ...

    def key_up(self, key: str) -> None: ...


class PlaybackState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"


class PlaybackEngine:
    def __init__(self, sink: KeySink, clock: Callable[[], float] = monotonic):
        self.sink = sink
        self.clock = clock
        self.state = PlaybackState.STOPPED
        self.duration = 0.0
        self.position = 0.0
        self._spans: tuple[MappedSpan, ...] = ()
        self._events: list[tuple[float, int, MappedSpan, str]] = []
        self._event_index = 0
        self._started_at = 0.0
        self._key_counts: dict[str, int] = {}

    def load(self, spans: list[MappedSpan] | tuple[MappedSpan, ...], duration: float) -> None:
        if duration < 0:
            raise ValueError("Playback duration cannot be negative.")
        self.reset()
        self.duration = duration
        self._spans = tuple(span for span in spans if span.end > span.start)
        events = []
        for span in self._spans:
            start = max(0.0, span.start)
            end = min(duration, span.end)
            if end <= start:
                continue
            for key in span.keys:
                events.append((start, 1, span, key))
                events.append((end, 0, span, key))
        self._events = sorted(events, key=lambda event: (event[0], event[1], event[3]))

    def play(self) -> None:
        if self.state is PlaybackState.PLAYING:
            return
        if self._key_counts:
            raise RuntimeError(
                "Cannot start playback while key releases are pending; reset playback first."
            )
        if self.state is PlaybackState.FINISHED:
            self.position = 0.0
            self._event_index = 0
        self._started_at = self.clock() - self.position
        if self.state is PlaybackState.PAUSED:
            for span in self._spans:
                if span.start <= self.position < span.end:
                    for key in span.keys:
                        self._press(key)
        self.state = PlaybackState.PLAYING

    def pause(self) -> None:
        if self.state is not PlaybackState.PLAYING:
            return
        self.tick()
        if self.state is PlaybackState.PLAYING:
            self.state = PlaybackState.PAUSED
            self._release_all()

    def reset(self) -> None:
        try:
            self._release_all()
        finally:
            self.state = PlaybackState.STOPPED
            self.position = 0.0
            self._event_index = 0
            self._started_at = 0.0

    def tick(self) -> float:
        if self.state is not PlaybackState.PLAYING:
            return self.position
        target = min(self.duration, max(self.position, self.clock() - self._started_at))
        while self._event_index < len(self._events) and self._events[self._event_index][0] <= target:
            _, is_start, _, key = self._events[self._event_index]
            if is_start:
                self._press(key)
            else:
                self._release(key)
            self._event_index += 1
        self.position = target
        if self.position >= self.duration:
            self._release_all()
            self.state = PlaybackState.FINISHED
        return self.position

    def _press(self, key: str) -> None:
        count = self._key_counts.get(key, 0)
        if count == 0:
            self.sink.key_down(key)
        self._key_counts[key] = count + 1

    def _release(self, key: str) -> None:
        count = self._key_counts.get(key, 0)
        if count <= 1:
            if count:
                self.sink.key_up(key)
            self._key_counts.pop(key, None)
        else:
            self._key_counts[key] = count - 1

    def _release_all(self) -> None:
        failures = []
        remaining = {}
        for key, count in self._key_counts.items():
            try:
                self.sink.key_up(key)
            except Exception as exc:
                failures.append(exc)
                remaining[key] = count
        self._key_counts = remaining
        if failures:
            raise failures[0]
