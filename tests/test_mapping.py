from genshin_midi.mapping import (
    NoteSpan,
    map_notes,
    map_voices,
    suggest_transposition,
    suggest_voice_transposition,
)


def test_standard_profile_maps_natural_scale_and_reports_accidentals():
    result = map_notes(
        [NoteSpan(0, 0.5, 48), NoteSpan(0.5, 1.0, 60), NoteSpan(1.0, 1.5, 61)],
        "standard",
    )

    assert [span.keys for span in result.spans] == [("Z",), ("A",)]
    assert len(result.warnings) == 1
    assert "61" in result.warnings[0]


def test_special_profile_uses_phrygian_scale_degrees():
    result = map_notes(
        [NoteSpan(0, 0.4, 48), NoteSpan(0.5, 0.9, 49), NoteSpan(1, 1.4, 51)],
        "special",
    )

    assert [span.keys for span in result.spans] == [("Z",), ("X",), ("C",)]
    assert not result.warnings


def test_guitar_maps_recognized_chord_and_falls_back_for_unknown_chord():
    recognized = map_notes(
        [NoteSpan(0, 0.5, pitch) for pitch in (60, 64, 67)],
        "guitar",
    )
    unknown = map_notes(
        [NoteSpan(0, 0.5, pitch) for pitch in (60, 63, 67)],
        "guitar",
    )

    assert len(recognized.spans) == 1
    assert recognized.spans[0].keys == ("Q",)
    assert recognized.spans[0].label == "C"
    assert len(unknown.spans) == 2
    assert any("未识别和弦" in warning for warning in unknown.warnings)


def test_transposition_happens_before_profile_range_and_scale_checks():
    result = map_notes([NoteSpan(0, 1, 61)], "standard", transpose=-1)

    assert result.spans[0].keys == ("A",)
    assert not result.warnings


def test_approximation_maps_missing_semitone_to_nearest_scale_pitch():
    strict = map_notes([NoteSpan(0, 1, 61)], "standard")
    approximate = map_notes([NoteSpan(0, 1, 61)], "standard", approximate=True)

    assert not strict.spans
    assert len(approximate.spans) == 1
    assert approximate.spans[0].keys == ("A",)
    assert approximate.spans[0].label == "近似到 MIDI 60"
    assert any("61" in warning and "60" in warning for warning in approximate.warnings)


def test_approximation_does_not_pull_out_of_range_notes_into_range():
    result = map_notes([NoteSpan(0, 1, 47)], "standard", approximate=True)

    assert not result.spans
    assert any("可演奏范围" in warning for warning in result.warnings)


def test_standard_instrument_approximates_chord_tones_as_simultaneous_keys():
    chord_notes = [NoteSpan(0, 0.5, pitch) for pitch in (61, 65, 68)]
    strict = map_notes(chord_notes, "standard")
    result = map_notes(chord_notes, "standard", approximate=True)

    assert [span.keys for span in strict.spans] == [("F",)]
    assert [span.keys for span in result.spans] == [("A",), ("F",), ("G",)]
    assert [span.start for span in result.spans] == [0, 0, 0]
    assert [span.end for span in result.spans] == [0.5, 0.5, 0.5]
    assert sum(span.label is not None for span in result.spans) == 2


def test_guitar_approximation_maps_unavailable_chord_and_reports_it():
    result = map_notes(
        [NoteSpan(0, 0.5, pitch) for pitch in (61, 65, 68)],
        "guitar",
        approximate=True,
    )

    assert len(result.spans) == 1
    assert result.spans[0].keys == ("W",)
    assert result.spans[0].label == "近似和弦 Dm"
    assert any("近似为 Dm" in warning for warning in result.warnings)



def test_approximation_mode_selects_individual_notes_or_nearest_guitar_chord():
    notes = [NoteSpan(0, 0.5, pitch) for pitch in (61, 65, 68)]

    single = map_notes(notes, "guitar", approximation_mode="single")
    chord = map_notes(notes, "guitar", approximation_mode="chord")

    assert {span.keys for span in single.spans} == {("Z",), ("V",), ("B",)}
    assert len(chord.spans) == 1
    assert chord.spans[0].keys == ("W",)


def test_chord_approximation_keeps_simultaneous_keys_on_single_note_profiles():
    notes = [NoteSpan(0, 0.5, pitch) for pitch in (61, 65, 68)]

    result = map_notes(notes, "standard", approximation_mode="chord")

    assert {span.keys for span in result.spans} == {("A",), ("F",), ("H",)}
    assert {span.start for span in result.spans} == {0}
    assert {span.end for span in result.spans} == {0.5}


def test_merged_voices_keep_independent_approximation_modes():
    single_notes = [NoteSpan(0, 0.5, pitch) for pitch in (61, 65, 68)]
    chord_notes = [NoteSpan(1, 1.5, pitch) for pitch in (61, 65, 68)]

    result = map_voices(
        (("single", single_notes, "single"), ("chord", chord_notes, "chord")),
        "guitar",
    )

    first_group = [span for span in result.spans if span.start == 0]
    second_group = [span for span in result.spans if span.start == 1]
    assert {span.keys for span in first_group} == {("Z",), ("V",), ("B",)}
    assert len(second_group) == 1
    assert second_group[0].keys == ("W",)


def test_chord_approximation_uses_transposed_pitch_classes():
    notes = [NoteSpan(0, 0.5, pitch) for pitch in (60, 64, 67)]

    guitar = map_notes(notes, "guitar", transpose=1, approximation_mode="chord")
    standard = map_notes(notes, "standard", transpose=1, approximation_mode="chord")

    assert len(guitar.spans) == 1
    assert guitar.spans[0].keys == ("W",)
    assert {span.keys for span in standard.spans} == {("A",), ("F",), ("H",)}
    assert all(span.source_pitches in {(60,), (64,), (67,)} for span in standard.spans)


def test_chord_approximation_turns_isolated_chromatic_note_into_chord():
    note = [NoteSpan(0, 0.5, 60)]

    guitar = map_notes(note, "guitar", transpose=1, approximation_mode="chord")
    standard = map_notes(note, "standard", transpose=1, approximation_mode="chord")
    single = map_notes(note, "standard", transpose=1, approximation_mode="single")

    assert guitar.spans[0].label.startswith("\u8fd1\u4f3c\u548c\u5f26")
    assert len(guitar.spans[0].keys) == 1
    assert len(standard.spans) == 1
    assert len(standard.spans[0].keys) == 3
    assert len(single.spans[0].keys) == 1


def test_nearest_guitar_chord_weights_repeated_octave_doubled_tones():
    notes = [NoteSpan(0, 0.5, pitch) for pitch in (60, 62, 74)]

    result = map_notes(notes, "guitar", approximation_mode="chord")

    assert len(result.spans) == 1
    assert result.spans[0].keys == ("T",)
    assert result.spans[0].label == "\u8fd1\u4f3c\u548c\u5f26 G"


def test_nearest_scale_chord_weights_repeated_pitch_classes():
    notes = [NoteSpan(0, 0.5, pitch) for pitch in (60, 72, 63, 65)]

    result = map_notes(notes, "standard", approximation_mode="chord")

    assert {span.keys for span in result.spans} == {("A",), ("Q",), ("D",)}


def test_auto_transposition_finds_nearest_shift_into_instrument_scale():
    f_sharp_major = [NoteSpan(0, 0.5, pitch) for pitch in (66, 68, 70, 71, 73, 75, 77)]

    assert suggest_transposition(f_sharp_major, "standard") == -6


def test_auto_transposition_prefers_exact_mapping_when_approximation_is_enabled():
    assert suggest_transposition(
        [NoteSpan(0, 1, 61)], "standard", approximate=True
    ) == -1


def test_map_voices_merges_notes_and_applies_approximation_per_voice():
    result = map_voices(
        (
            ("strict", [NoteSpan(0, 0.5, 61)], False),
            ("approx", [NoteSpan(0, 0.75, 61)], True),
        ),
        "standard",
    )

    assert len(result.spans) == 1
    assert result.spans[0].keys == ("A",)
    assert result.spans[0].start == 0
    assert result.spans[0].end == 0.75
    assert any("strict" in warning and "61" in warning for warning in result.warnings)
    assert any("approx" in warning and "60" in warning for warning in result.warnings)


def test_map_voices_merges_exact_notes_from_multiple_tracks():
    result = map_voices(
        (
            ("melody", [NoteSpan(0, 0.4, 60)], False),
            ("bass", [NoteSpan(0, 0.8, 48)], False),
        ),
        "standard",
    )

    assert [span.keys for span in result.spans] == [("A",), ("Z",)]
    assert [span.end for span in result.spans] == [0.4, 0.8]
    assert not result.warnings


def test_auto_transposition_scores_selected_voices_together():
    voices = (
        ("lead", [NoteSpan(0, 1, 61)], False),
        ("bass", [NoteSpan(0, 1, 61)], True),
    )

    assert suggest_voice_transposition(voices, "standard") == -1
