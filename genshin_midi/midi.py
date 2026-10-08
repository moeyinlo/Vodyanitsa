from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

import mido


@dataclass(frozen=True)
class NoteSpan:
    start: float
    end: float
    pitch: int
    channel: int = 0


@dataclass(frozen=True)
class MidiTrack:
    index: int
    name: str
    notes: tuple[NoteSpan, ...]

    @property
    def pitch_range(self) -> tuple[int, int] | None:
        if not self.notes:
            return None
        pitches = [note.pitch for note in self.notes]
        return min(pitches), max(pitches)


@dataclass(frozen=True)
class TempoEvent:
    tick: int
    bpm: float


@dataclass(frozen=True)
class MidiDocument:
    duration: float
    ticks_per_beat: int
    tracks: tuple[MidiTrack, ...]
    tempo_events: tuple[TempoEvent, ...]
    time_signature: tuple[int, int]
    warnings: tuple[str, ...]


def _tempo_timeline(
    midi: mido.MidiFile,
) -> tuple[list[int], list[float], list[int], int, dict[int, int]]:
    absolute_tempo: dict[int, int] = {0: 500_000}
    tick = 0
    for message in mido.merge_tracks(midi.tracks):
        tick += message.time
        if message.type == "set_tempo":
            absolute_tempo[tick] = message.tempo
    total_ticks = tick

    ticks: list[int] = []
    seconds: list[float] = []
    tempos: list[int] = []
    current_tick = 0
    current_seconds = 0.0
    current_tempo = 500_000
    for change_tick, new_tempo in sorted(absolute_tempo.items()):
        current_seconds += mido.tick2second(
            change_tick - current_tick, midi.ticks_per_beat, current_tempo
        )
        current_tick = change_tick
        current_tempo = new_tempo
        ticks.append(change_tick)
        seconds.append(current_seconds)
        tempos.append(current_tempo)
    return ticks, seconds, tempos, total_ticks, absolute_tempo


def _to_seconds(
    tick: int, ticks_per_beat: int, tempo_ticks: list[int], tempo_seconds: list[float], tempos: list[int]
) -> float:
    index = max(0, bisect_right(tempo_ticks, tick) - 1)
    return tempo_seconds[index] + mido.tick2second(
        tick - tempo_ticks[index], ticks_per_beat, tempos[index]
    )


def load_midi(source: str | Path | mido.MidiFile) -> MidiDocument:
    midi = source if isinstance(source, mido.MidiFile) else mido.MidiFile(str(source))
    tempo_ticks, tempo_seconds, tempos, total_ticks, absolute_tempos = _tempo_timeline(midi)
    duration = _to_seconds(total_ticks, midi.ticks_per_beat, tempo_ticks, tempo_seconds, tempos)
    warnings: list[str] = []
    parsed_tracks: list[MidiTrack] = []
    time_signature = (4, 4)
    for track in midi.tracks:
        signature = next(
            (message for message in track if message.type == "time_signature"), None
        )
        if signature:
            time_signature = (signature.numerator, signature.denominator)
            break

    for index, track in enumerate(midi.tracks):
        name = next(
            (message.name for message in track if message.type == "track_name"),
            f"Track {index}",
        )
        tick = 0
        active: dict[tuple[int, int], deque[int]] = defaultdict(deque)
        spans: list[NoteSpan] = []
        for message in track:
            tick += message.time
            if message.type == "note_on" and message.velocity > 0:
                active[(message.channel, message.note)].append(tick)
            elif message.type == "note_off" or (
                message.type == "note_on" and message.velocity == 0
            ):
                queue = active[(message.channel, message.note)]
                if not queue:
                    warnings.append(
                        f"轨道 {index}（{name}）的音高 {message.note} 存在未配对的 note-off。"
                    )
                    continue
                start_tick = queue.popleft()
                spans.append(
                    NoteSpan(
                        _to_seconds(start_tick, midi.ticks_per_beat, tempo_ticks, tempo_seconds, tempos),
                        _to_seconds(tick, midi.ticks_per_beat, tempo_ticks, tempo_seconds, tempos),
                        message.note,
                        message.channel,
                    )
                )
        for (channel, pitch), starts in active.items():
            while starts:
                start_tick = starts.popleft()
                spans.append(
                    NoteSpan(
                        _to_seconds(start_tick, midi.ticks_per_beat, tempo_ticks, tempo_seconds, tempos),
                        duration,
                        pitch,
                        channel,
                    )
                )
                warnings.append(
                    f"轨道 {index}（{name}）的音高 {pitch} 缺少 note-off，已在曲尾结束。"
                )
        parsed_tracks.append(
            MidiTrack(index, name, tuple(sorted(spans, key=lambda note: (note.start, note.pitch))))
        )

    tempo_events = tuple(
        TempoEvent(tick, mido.tempo2bpm(tempo))
        for tick, tempo in sorted(absolute_tempos.items())
    )
    return MidiDocument(
        duration,
        midi.ticks_per_beat,
        tuple(parsed_tracks),
        tempo_events,
        time_signature,
        tuple(warnings),
    )
