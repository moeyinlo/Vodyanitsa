from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .midi import NoteSpan


@dataclass(frozen=True)
class InstrumentProfile:
    id: str
    name: str
    scale_intervals: tuple[int, ...]
    base_midi: int
    note_keys: tuple[str, ...]
    chord_keys: dict[str, str] | None = None


@dataclass(frozen=True)
class MappedSpan:
    start: float
    end: float
    keys: tuple[str, ...]
    source_pitches: tuple[int, ...] = ()
    label: str | None = None


@dataclass(frozen=True)
class MappingResult:
    spans: tuple[MappedSpan, ...]
    warnings: tuple[str, ...]


MAJOR = (0, 2, 4, 5, 7, 9, 11)
PHRYGIAN = (0, 1, 3, 5, 7, 8, 10)
_CHORD_KEYS = {"C": "Q", "Dm": "W", "Em": "E", "F": "R", "G": "T", "Am": "Y", "G7": "U"}
_CHORD_INTERVALS = {
    frozenset((0, 4, 7)): "C",
    frozenset((2, 5, 9)): "Dm",
    frozenset((4, 7, 11)): "Em",
    frozenset((0, 5, 9)): "F",
    frozenset((2, 7, 11)): "G",
    frozenset((0, 4, 9)): "Am",
    frozenset((2, 5, 7, 11)): "G7",
}

PROFILES = (
    InstrumentProfile(
        "standard", "标准音部（三排）", MAJOR, 48,
        tuple("ZXCVBNM" + "ASDFGHJ" + "QWERTYU"),
    ),
    InstrumentProfile(
        "guitar", "类吉他（和弦 + 单音）", MAJOR, 60,
        tuple("ZXCVBNM" + "ASDFGHJ"), _CHORD_KEYS,
    ),
    InstrumentProfile(
        "special", "特殊调式（弗里吉亚）", PHRYGIAN, 48,
        tuple("ZXCVBNM" + "ASDFGHJ" + "QWERTYU"),
    ),
    InstrumentProfile(
        "voice", "女声 / 中低音部（双排）", MAJOR, 60,
        tuple("ASDFGHJ" + "QWERTYU"),
    ),
)
_PROFILE_BY_ID = {profile.id: profile for profile in PROFILES}


def get_profile(profile_id: str) -> InstrumentProfile:
    try:
        return _PROFILE_BY_ID[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown instrument profile: {profile_id}") from exc


def _key_for_pitch(pitch: int, profile: InstrumentProfile) -> str | None:
    offset = pitch - profile.base_midi
    if offset < 0:
        return None
    octave, pitch_class = divmod(offset, 12)
    try:
        degree = profile.scale_intervals.index(pitch_class)
    except ValueError:
        return None
    key_index = octave * len(profile.scale_intervals) + degree
    return profile.note_keys[key_index] if key_index < len(profile.note_keys) else None


def _pitch_for_key_index(index: int, profile: InstrumentProfile) -> int:
    octave, degree = divmod(index, len(profile.scale_intervals))
    return profile.base_midi + octave * 12 + profile.scale_intervals[degree]


def _nearest_chord(
    notes: list[NoteSpan], transpose: int, *, allow_partial: bool = False
) -> str | None:
    source_pitches = frozenset((note.pitch + transpose) % 12 for note in notes)
    if not source_pitches or (len(source_pitches) < 3 and not allow_partial):
        return None

    def pitch_class_distance(left: int, right: int) -> int:
        distance = abs(left - right)
        return min(distance, 12 - distance)

    candidates = []
    for intervals, chord_name in _CHORD_INTERVALS.items():
        source_to_chord = sum(
            min(pitch_class_distance(source, target) for target in intervals)
            for source in source_pitches
        )
        chord_to_source = sum(
            min(pitch_class_distance(target, source) for source in source_pitches)
            for target in intervals
        )
        candidates.append((source_to_chord + chord_to_source, chord_name))
    return min(candidates)[1]


def _nearest_scale_chord(
    notes: list[NoteSpan], transpose: int, profile: InstrumentProfile
) -> frozenset[int]:
    source = frozenset((note.pitch + transpose) % 12 for note in notes)
    intervals = profile.scale_intervals
    candidates = {
        frozenset(
            (
                intervals[(degree + offset) % len(intervals)]
                + 12 * ((degree + offset) // len(intervals))
            )
            % 12
            for offset in (0, 2, 4)
        )
        for degree in range(len(intervals))
    }

    def distance(left: int, right: int) -> int:
        delta = abs(left - right)
        return min(delta, 12 - delta)

    return min(
        candidates,
        key=lambda chord: (
            sum(min(distance(pitch, target) for target in chord) for pitch in source)
            + sum(min(distance(target, pitch) for pitch in source) for target in chord),
            tuple(sorted(chord)),
        ),
    )


def _recognize_chord(notes: list[NoteSpan], transpose: int) -> str | None:
    pitches = frozenset((note.pitch + transpose) % 12 for note in notes)
    if len(pitches) < 3:
        return None
    return _CHORD_INTERVALS.get(pitches)


def _map_single(
    note: NoteSpan,
    profile: InstrumentProfile,
    transpose: int,
    warnings: list[str],
    approximate: bool,
) -> MappedSpan | None:
    transposed_pitch = note.pitch + transpose
    key = _key_for_pitch(transposed_pitch, profile)
    if key is None:
        if approximate and profile.note_keys:
            low = _pitch_for_key_index(0, profile)
            high = _pitch_for_key_index(len(profile.note_keys) - 1, profile)
            if low <= transposed_pitch <= high:
                playable_pitches = tuple(
                    _pitch_for_key_index(index, profile)
                    for index in range(len(profile.note_keys))
                )
                played_pitch = min(
                    playable_pitches,
                    key=lambda pitch: (abs(pitch - transposed_pitch), pitch),
                )
                key = _key_for_pitch(played_pitch, profile)
                assert key is not None
                difference = played_pitch - transposed_pitch
                warnings.append(
                    f"音高 {note.pitch} 转调后为 {transposed_pitch}，近似映射到 MIDI "
                    f"{played_pitch}（偏差 {difference:+d} 半音）。"
                )
                return MappedSpan(
                    note.start,
                    note.end,
                    (key,),
                    (note.pitch,),
                    f"近似到 MIDI {played_pitch}",
                )
        warnings.append(
            f"音高 {note.pitch} 转调后为 {transposed_pitch}，不在{profile.name}可演奏范围内。"
        )
        return None
    return MappedSpan(note.start, note.end, (key,), (note.pitch,))


def map_notes(
    notes: Iterable[NoteSpan],
    profile_id: str,
    transpose: int = 0,
    chord_window: float = 0.045,
    *,
    approximate: bool = False,
    approximation_mode: str | None = None,
) -> MappingResult:
    profile = get_profile(profile_id)
    if approximation_mode is None:
        approximation_mode = "chord" if approximate and profile.chord_keys else (
            "single" if approximate else "none"
        )
    if approximation_mode not in {"none", "single", "chord"}:
        raise ValueError(f"Unknown approximation mode: {approximation_mode}")
    approximate = approximation_mode != "none"
    ordered = sorted(notes, key=lambda note: (note.start, note.pitch))
    warnings: list[str] = []
    spans: list[MappedSpan] = []

    groups: list[list[NoteSpan]] = []
    for note in ordered:
        if not groups or note.start - groups[-1][0].start > chord_window:
            groups.append([note])
        else:
            groups[-1].append(note)

    for group in groups:
        if (
            profile.chord_keys
            and approximation_mode == "chord"
            and len(group) == 1
            and _key_for_pitch(group[0].pitch + transpose, profile) is None
        ):
            source_pitch = group[0].pitch + transpose
            low = _pitch_for_key_index(0, profile)
            high = _pitch_for_key_index(len(profile.note_keys) - 1, profile)
            if low <= source_pitch <= high:
                chord_name = _nearest_chord(group, transpose, allow_partial=True)
                if chord_name:
                    spans.append(
                        MappedSpan(
                            group[0].start,
                            group[0].end,
                            (profile.chord_keys[chord_name],),
                            (group[0].pitch,),
                            f"\u8fd1\u4f3c\u548c\u5f26 {chord_name}",
                        )
                    )
                    warnings.append(
                        f"MIDI {source_pitch} \u4e0d\u5728\u97f3\u9636\u4e2d\uff0c"
                        f"\u5df2\u8fd1\u4f3c\u4e3a\u548c\u5f26 {chord_name}\u3002"
                    )
                    continue
        if profile.chord_keys and len(group) > 1:
            chord_name = _recognize_chord(group, transpose)
            if chord_name:
                spans.append(
                    MappedSpan(
                        min(note.start for note in group),
                        max(note.end for note in group),
                        (profile.chord_keys[chord_name],),
                        tuple(note.pitch for note in group),
                        chord_name,
                    )
                )
                continue
            pitches = ", ".join(str(note.pitch + transpose) for note in group)
            if approximate:
                chord_name = (
                    _nearest_chord(group, transpose)
                    if approximation_mode == "chord"
                    else None
                )
                if chord_name:
                    spans.append(
                        MappedSpan(
                            min(note.start for note in group),
                            max(note.end for note in group),
                            (profile.chord_keys[chord_name],),
                            tuple(note.pitch for note in group),
                            f"近似和弦 {chord_name}",
                        )
                    )
                    warnings.append(f"未识别和弦（{pitches}），近似为 {chord_name}。")
                    continue
            warnings.append(f"未识别和弦（{pitches}），将尝试映射为单音。")
        if (
            approximation_mode == "chord"
            and not profile.chord_keys
            and any(_key_for_pitch(note.pitch + transpose, profile) is None for note in group)
        ):
            chord = _nearest_scale_chord(group, transpose, profile)
            playable = tuple(
                _pitch_for_key_index(index, profile)
                for index in range(len(profile.note_keys))
                if _pitch_for_key_index(index, profile) % 12 in chord
            )
            if len(group) == 1:
                note = group[0]
                source_pitch = note.pitch + transpose
                low = _pitch_for_key_index(0, profile)
                high = _pitch_for_key_index(len(profile.note_keys) - 1, profile)
                if low <= source_pitch <= high:
                    chord_pitches = tuple(
                        min(
                            (pitch for pitch in playable if pitch % 12 == pitch_class),
                            key=lambda pitch: (abs(pitch - source_pitch), pitch),
                        )
                        for pitch_class in sorted(chord)
                    )
                    chord_keys = tuple(
                        key
                        for pitch in chord_pitches
                        if (key := _key_for_pitch(pitch, profile)) is not None
                    )
                    if chord_keys:
                        spans.append(
                            MappedSpan(
                                note.start,
                                note.end,
                                chord_keys,
                                (note.pitch,),
                                "\u8fd1\u4f3c\u548c\u5f26\u97f3",
                            )
                        )
                        warnings.append(
                            f"MIDI {source_pitch} \u4e0d\u5728\u97f3\u9636\u4e2d\uff0c"
                            "\u5df2\u6269\u5c55\u4e3a\u6700\u63a5\u8fd1\u7684\u8c03\u5185\u548c\u5f26\u3002"
                        )
                        continue
                mapped = _map_single(note, profile, transpose, warnings, approximate)
                if mapped:
                    spans.append(mapped)
                continue
            for note in group:
                source_pitch = note.pitch + transpose
                played_pitch = min(
                    playable,
                    key=lambda pitch: (abs(pitch - source_pitch), pitch),
                )
                key = _key_for_pitch(played_pitch, profile)
                assert key is not None
                changed = played_pitch != source_pitch
                spans.append(
                    MappedSpan(
                        note.start,
                        note.end,
                        (key,),
                        (note.pitch,),
                        "\u548c\u5f26\u97f3\u8fd1\u4f3c" if changed else None,
                    )
                )
                if changed:
                    warnings.append(
                        f"\u548c\u5f26\u8fd1\u4f3c\uff1aMIDI {source_pitch} "
                        f"\u6620\u5c04\u5230 {played_pitch}\u3002"
                    )
            continue
        for note in group:
            mapped = _map_single(note, profile, transpose, warnings, approximate)
            if mapped:
                spans.append(mapped)

    return MappingResult(
        tuple(sorted(spans, key=lambda span: (span.start, span.keys))),
        tuple(warnings),
    )


def map_voices(
    voices: Iterable[tuple[str, Iterable[NoteSpan], bool | str]],
    profile_id: str,
    transpose: int = 0,
) -> MappingResult:
    spans: list[MappedSpan] = []
    warnings: list[str] = []
    for voice_name, notes, mode in voices:
        legacy_approximate = mode if isinstance(mode, bool) else False
        approximation_mode = None if isinstance(mode, bool) else mode
        result = map_notes(
            notes,
            profile_id,
            transpose,
            approximate=legacy_approximate,
            approximation_mode=approximation_mode,
        )
        spans.extend(result.spans)
        warnings.extend(f"[{voice_name}] {warning}" for warning in result.warnings)
    return MappingResult(
        tuple(sorted(spans, key=lambda span: (span.start, span.keys))),
        tuple(warnings),
    )


def suggest_transposition(
    notes: Iterable[NoteSpan],
    profile_id: str,
    minimum: int = -24,
    maximum: int = 24,
    *,
    approximate: bool = False,
) -> int:
    if minimum > maximum:
        raise ValueError("Minimum transposition must not exceed maximum.")
    source_notes = tuple(notes)
    candidates = []
    for offset in range(minimum, maximum + 1):
        result = map_notes(source_notes, profile_id, offset, approximate=approximate)
        mapped_notes = sum(len(span.source_pitches) for span in result.spans)
        candidates.append((-mapped_notes, len(result.warnings), abs(offset), offset))
    return min(candidates)[3]


def suggest_voice_transposition(
    voices: Iterable[tuple[str, Iterable[NoteSpan], bool | str]],
    profile_id: str,
    minimum: int = -24,
    maximum: int = 24,
) -> int:
    if minimum > maximum:
        raise ValueError("Minimum transposition must not exceed maximum.")
    source_voices = tuple((name, tuple(notes), mode) for name, notes, mode in voices)
    candidates = []
    for offset in range(minimum, maximum + 1):
        result = map_voices(source_voices, profile_id, offset)
        mapped_notes = sum(len(span.source_pitches) for span in result.spans)
        candidates.append((-mapped_notes, len(result.warnings), abs(offset), offset))
    return min(candidates)[3]
