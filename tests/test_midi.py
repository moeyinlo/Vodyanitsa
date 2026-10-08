import mido

from genshin_midi.midi import load_midi


def test_tempo_changes_note_durations_and_rests_are_preserved():
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=500_000, time=0))
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=1_000_000, time=480))
    midi.tracks.append(tempo_track)

    notes = mido.MidiTrack()
    notes.append(mido.MetaMessage("track_name", name="Melody", time=0))
    notes.append(mido.Message("note_on", note=60, velocity=90, time=0))
    notes.append(mido.Message("note_off", note=60, velocity=0, time=960))
    notes.append(mido.Message("note_on", note=62, velocity=80, time=480))
    notes.append(mido.Message("note_off", note=62, velocity=0, time=480))
    midi.tracks.append(notes)

    song = load_midi(midi)
    melody = song.tracks[1]

    assert song.duration == 3.5
    assert [(note.pitch, note.start, note.end) for note in melody.notes] == [
        (60, 0.0, 1.5),
        (62, 2.5, 3.5),
    ]
    assert song.time_signature == (4, 4)


def test_unmatched_note_on_is_closed_at_end_of_song():
    midi = mido.MidiFile(type=0, ticks_per_beat=96)
    track = mido.MidiTrack()
    track.append(mido.Message("note_on", note=60, velocity=90, time=0))
    track.append(mido.MetaMessage("end_of_track", time=96))
    midi.tracks.append(track)

    song = load_midi(midi)

    assert len(song.tracks[0].notes) == 1
    assert song.tracks[0].notes[0].end == song.duration
    assert song.warnings
