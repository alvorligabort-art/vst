from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from house_loop_maker import simple_midi


def _write_test_midi(path: Path) -> None:
    tempo = 118.0
    instrument = simple_midi.MidiInstrument(
        name="Test Piano",
        program=simple_midi.instrument_name_to_program("Acoustic Grand Piano"),
        channel=0,
    )

    bar_length = 60.0 / tempo * 4.0
    chords = [
        [60, 64, 67],  # C major
        [62, 65, 69],  # D minor
        [55, 59, 62],  # G major
        [57, 60, 64],  # A minor
    ]
    for index, chord in enumerate(chords):
        start = index * bar_length
        end = start + bar_length
        for pitch in chord:
            instrument.notes.append(
                simple_midi.MidiNote(pitch=pitch, start=start, end=end, velocity=90)
            )

    midi = simple_midi.SimpleMidiFile(
        tempo=tempo,
        ticks_per_quarter=480,
        instruments=[instrument],
    )
    midi.write(path)


def test_cli_generates_eight_bar_loop(tmp_path: Path) -> None:
    source = tmp_path / "source.mid"
    output = tmp_path / "loop.mid"
    _write_test_midi(source)

    cmd = [
        sys.executable,
        "-m",
        "house_loop_maker",
        str(source),
        str(output),
        "--mode",
        "euphoric",
        "--seed",
        "7",
    ]
    subprocess.run(cmd, check=True)

    assert output.exists()

    loaded = simple_midi.load_midi(output)
    assert loaded.notes, "Generated MIDI should contain notes"

    expected_tempo = 118.0
    expected_length = 60.0 / expected_tempo * 4.0 * 8
    actual_length = max(note.end for note in loaded.notes)
    assert expected_length - 1.0 <= actual_length <= expected_length + 1.0

    total_notes = len(loaded.notes)
    assert total_notes > 40
    has_long = any((note.end - note.start) > 1.5 for note in loaded.notes)
    has_short = any((note.end - note.start) < 0.5 for note in loaded.notes)
    assert has_long and has_short
