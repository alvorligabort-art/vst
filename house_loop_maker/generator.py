"""Core logic for converting source MIDI files into 8-bar house loops."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Union
import math
import random
import statistics
from collections import Counter

from . import simple_midi


@dataclass
class HouseLoopOptions:
    """Configuration for the loop generator."""

    mode: str = "auto"
    swing: float = 0.12
    seed: Optional[int] = None
    tempo: Optional[float] = None
    target_bars: int = 8


@dataclass
class NoteInfo:
    """Lightweight container describing a MIDI note."""

    pitch: int
    start: float
    end: float
    velocity: int

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class ChordShape:
    """Represents the material for a single bar in the new loop."""

    root_pc: int
    pitches: List[int]
    label: str


@dataclass
class HouseLoopResult:
    """Bundle containing the generated MIDI and metadata about the loop."""

    midi: simple_midi.SimpleMidiFile
    chords: Sequence[ChordShape]
    tempo: float
    mode: str


ModeType = Union[str, None]


def generate_house_loop(
    source: Union[str, Path, simple_midi.LoadedMidi],
    options: HouseLoopOptions,
) -> HouseLoopResult:
    """Generate an 8-bar house loop from ``source`` according to ``options``.

    Parameters
    ----------
    source:
        Either a path to a MIDI file or an already loaded :class:`~house_loop_maker.simple_midi.LoadedMidi`
        instance containing the material to transform.
    options:
        Settings describing how the resulting loop should feel.

    Returns
    -------
    HouseLoopResult
        Metadata and the generated MIDI data for the new loop.
    """

    rng = random.Random(options.seed)
    loaded = _load_midi(source)
    tempo = _resolve_tempo(loaded, options.tempo)

    note_infos = _collect_notes(loaded)
    bar_length = 60.0 / tempo * 4.0
    beat_length = 60.0 / tempo
    mode = _resolve_mode(options.mode, note_infos)

    base_register = _estimate_register(note_infos)
    base_roots = _extract_roots(note_infos, bar_length, options.target_bars)

    if not base_roots:
        base_roots = _default_roots(mode)

    progression_roots = _expand_roots(base_roots, options.target_bars, mode, rng)
    chords = [_build_chord(root, base_register, mode, rng) for root in progression_roots]

    loop = _render_loop(chords, tempo, options.swing, beat_length, bar_length, rng)
    return HouseLoopResult(midi=loop, chords=chords, tempo=tempo, mode=mode)


def _load_midi(source: Union[str, Path, simple_midi.LoadedMidi]) -> simple_midi.LoadedMidi:
    if isinstance(source, simple_midi.LoadedMidi):
        return source
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"MIDI file not found: {path}")
    return simple_midi.load_midi(path)


def _resolve_tempo(loaded: simple_midi.LoadedMidi, override: Optional[float]) -> float:
    if override is not None and override > 0:
        return float(override)
    tempo = loaded.tempo
    if not math.isfinite(tempo) or tempo <= 0:
        tempo = 124.0
    return tempo


def _collect_notes(loaded: simple_midi.LoadedMidi) -> List[NoteInfo]:
    notes = [
        NoteInfo(
            pitch=int(note.pitch),
            start=float(note.start),
            end=float(note.end),
            velocity=int(note.velocity),
        )
        for note in loaded.notes
    ]
    notes.sort(key=lambda n: (n.start, n.pitch))
    return notes


def _resolve_mode(mode_arg: ModeType, note_infos: Sequence[NoteInfo]) -> str:
    if mode_arg and mode_arg not in {"auto", "euphoric", "minor_fifth"}:
        raise ValueError(
            "mode must be one of 'auto', 'euphoric', or 'minor_fifth'"
        )
    if mode_arg and mode_arg != "auto":
        return mode_arg

    pitch_classes = [note.pitch % 12 for note in note_infos]
    if not pitch_classes:
        return "euphoric"

    major_thirds = 0
    minor_thirds = 0
    pcs = set(pitch_classes)
    for pc in pcs:
        if (pc + 4) % 12 in pcs:
            major_thirds += 1
        if (pc + 3) % 12 in pcs:
            minor_thirds += 1
    if minor_thirds > major_thirds:
        return "minor_fifth"
    return "euphoric"


def _estimate_register(note_infos: Sequence[NoteInfo]) -> int:
    if not note_infos:
        return 48  # Around C3
    average_pitch = statistics.fmean(note.pitch for note in note_infos)
    register = int(round(average_pitch / 12.0) * 12)
    register = max(36, min(60, register))
    return register


def _extract_roots(
    note_infos: Sequence[NoteInfo],
    bar_length: float,
    target_bars: int,
) -> List[int]:
    if not note_infos:
        return []
    bars: List[List[int]] = [[] for _ in range(target_bars)]
    for note in note_infos:
        start_bar = int(note.start // bar_length)
        if start_bar >= target_bars:
            continue
        end_bar = int(math.ceil(note.end / bar_length))
        end_bar = min(end_bar, target_bars)
        for bar in range(start_bar, end_bar):
            weight = max(1, int(round(note.duration / (bar_length / 4.0))))
            bars[bar].extend([note.pitch % 12] * weight)
    roots: List[int] = []
    previous_root = 0
    any_content = False
    for bar_notes in bars:
        if not bar_notes:
            roots.append(previous_root)
            continue
        any_content = True
        counts = Counter(bar_notes)
        root_pc = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]
        roots.append(root_pc)
        previous_root = root_pc
    return roots if any_content else []


def _default_roots(mode: str) -> List[int]:
    if mode == "minor_fifth":
        return [9, 4, 11, 7]  # A minor, E minor, B minor, G major
    return [0, 7, 9, 5]  # C major, G major, A minor, F major


def _expand_roots(
    base_roots: Sequence[int],
    target_bars: int,
    mode: str,
    rng: random.Random,
) -> List[int]:
    if not base_roots:
        base_roots = _default_roots(mode)
    adjustments = {
        "euphoric": [0, 2, 4, 5, 7, -3],
        "minor_fifth": [0, 3, 5, 7, 10, -5],
    }[mode]
    progression: List[int] = []
    previous = base_roots[0] % 12
    for index in range(target_bars):
        root = base_roots[index % len(base_roots)] % 12
        if rng.random() < 0.35:
            root = (root + rng.choice(adjustments)) % 12
        if progression and rng.random() < 0.2:
            # small leading-tone lift for additional euphoria
            root = (progression[-1] + rng.choice([2, 5, 7])) % 12
        if progression and progression[-1] == root and rng.random() < 0.4:
            root = (root + rng.choice([5, 7, 9])) % 12
        previous = root
        progression.append(previous)
    return progression


def _build_chord(
    root_pc: int,
    base_register: int,
    mode: str,
    rng: random.Random,
) -> ChordShape:
    if mode == "euphoric":
        templates = [
            ("maj7", [0, 4, 7, 11]),
            ("add9", [0, 2, 7, 9]),
            ("sixnine", [0, 4, 7, 9, 14]),
            ("suslift", [0, 5, 7, 9, 14]),
        ]
    else:
        templates = [
            ("min7", [0, 3, 7, 10]),
            ("min9", [0, 3, 7, 10, 14]),
            ("power", [0, 7, 12]),
            ("darkpad", [0, 3, 5, 10, 14]),
        ]
    label, intervals = rng.choice(templates)
    root_note = base_register + root_pc
    while root_note < 36:
        root_note += 12
    while root_note > 60:
        root_note -= 12
    chord_pitches = []
    for interval in intervals:
        pitch = root_note + interval
        if pitch < 0:
            pitch = (pitch % 12) + 12
        if pitch > 108:
            pitch -= 12 * ((pitch - 96) // 12 + 1)
        chord_pitches.append(pitch)
    # Ensure unique, sorted pitches
    unique_pitches = sorted(set(chord_pitches))
    # Additional shimmer
    if rng.random() < 0.55:
        top_pitch = unique_pitches[-1] + 12
        if top_pitch <= 108:
            unique_pitches.append(top_pitch)
    return ChordShape(root_pc=root_pc, pitches=unique_pitches, label=label)


def _render_loop(
    chords: Sequence[ChordShape],
    tempo: float,
    swing: float,
    beat_length: float,
    bar_length: float,
    rng: random.Random,
) -> simple_midi.SimpleMidiFile:
    swing = max(0.0, min(0.4, swing))

    stabs = simple_midi.MidiInstrument(
        name="House Stabs",
        program=simple_midi.instrument_name_to_program("SynthBrass 1"),
        channel=0,
    )
    plucks = simple_midi.MidiInstrument(
        name="Pluck Arp",
        program=simple_midi.instrument_name_to_program("Lead 1 (square)"),
        channel=1,
    )
    pads = simple_midi.MidiInstrument(
        name="Airy Pad",
        program=simple_midi.instrument_name_to_program("Synth Pad 2 (warm)"),
        channel=2,
    )

    for bar_index, chord in enumerate(chords):
        bar_start = bar_index * bar_length
        bar_end = bar_start + bar_length

        _render_stabs(stabs, chord, bar_start, bar_end, beat_length, swing, rng)
        _render_plucks(plucks, chord, bar_start, bar_end, beat_length, swing, rng)
        _render_pads(pads, chord, bar_start, bar_end, rng)

    midi = simple_midi.SimpleMidiFile(
        tempo=tempo,
        ticks_per_quarter=480,
        instruments=[stabs, plucks, pads],
    )
    return midi


def _apply_swing(start_time: float, beat_position: float, beat_length: float, swing: float) -> float:
    eighth_index = int(round(beat_position * 2))
    if eighth_index % 2 == 1:
        return start_time + swing * beat_length * 0.5
    return start_time


def _render_stabs(
    instrument: simple_midi.MidiInstrument,
    chord: ChordShape,
    bar_start: float,
    bar_end: float,
    beat_length: float,
    swing: float,
    rng: random.Random,
) -> None:
    base_pattern = [0.0, 0.5, 1.5, 2.5, 3.5]
    pattern = list(base_pattern)
    if rng.random() < 0.4:
        pattern.append(2.0)
    if rng.random() < 0.3 and 0.0 in pattern:
        pattern.remove(0.0)
    pattern.sort()

    for step_index, beat in enumerate(pattern):
        start = bar_start + beat * beat_length
        start = _apply_swing(start, beat, beat_length, swing)
        duration = min(beat_length * 0.35, bar_end - start - 0.01)
        if duration <= 0:
            continue
        velocity = int(75 + rng.random() * 35)
        for pitch in chord.pitches:
            vel = max(0, min(127, velocity + rng.randint(-5, 5)))
            instrument.notes.append(
                simple_midi.MidiNote(
                    pitch=pitch,
                    start=start,
                    end=start + duration,
                    velocity=vel,
                )
            )


def _render_plucks(
    instrument: simple_midi.MidiInstrument,
    chord: ChordShape,
    bar_start: float,
    bar_end: float,
    beat_length: float,
    swing: float,
    rng: random.Random,
) -> None:
    pattern = [i * 0.5 for i in range(8)]  # 1/8th notes across the bar
    chord_cycle = chord.pitches
    if rng.random() < 0.5:
        chord_cycle = [p + 12 for p in chord_cycle if p + 12 <= 115]
    if not chord_cycle:
        chord_cycle = chord.pitches

    for idx, beat in enumerate(pattern):
        start = bar_start + beat * beat_length
        start = _apply_swing(start, beat, beat_length, swing * 0.8)
        duration = min(beat_length * 0.45, bar_end - start - 0.01)
        if duration <= 0:
            continue
        pitch = chord_cycle[idx % len(chord_cycle)]
        # occasional octave jumps
        if rng.random() < 0.25 and pitch + 12 <= 115:
            pitch += 12
        velocity = int(60 + rng.random() * 30)
        instrument.notes.append(
            simple_midi.MidiNote(
                velocity=max(0, min(127, velocity)),
                pitch=pitch,
                start=start,
                end=start + duration,
            )
        )


def _render_pads(
    instrument: simple_midi.MidiInstrument,
    chord: ChordShape,
    bar_start: float,
    bar_end: float,
    rng: random.Random,
) -> None:
    start = bar_start
    end = bar_end - 0.05
    velocity = int(50 + rng.random() * 20)
    for pitch in chord.pitches:
        pad_pitch = pitch
        if rng.random() < 0.35 and pad_pitch - 12 >= 36:
            pad_pitch -= 12
        instrument.notes.append(
            simple_midi.MidiNote(
                velocity=max(0, min(127, velocity)),
                pitch=pad_pitch,
                start=start,
                end=end,
            )
        )
