"""A tiny MIDI reader/writer tailored for the house loop generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


@dataclass
class MidiNote:
    pitch: int
    start: float  # seconds
    end: float  # seconds
    velocity: int


@dataclass
class MidiInstrument:
    name: str
    program: int
    channel: int
    notes: List[MidiNote] = field(default_factory=list)


@dataclass
class LoadedMidi:
    tempo: float
    ticks_per_quarter: int
    notes: List[MidiNote]


@dataclass
class SimpleMidiFile:
    tempo: float
    ticks_per_quarter: int
    instruments: List[MidiInstrument]

    def write(self, path: Union[str, Path]) -> None:
        path = Path(path)
        data = _encode_midi(self)
        path.write_bytes(data)


GM_PROGRAMS: Dict[str, int] = {
    "Acoustic Grand Piano": 0,
    "SynthBrass 1": 62,
    "Lead 1 (square)": 80,
    "Synth Pad 2 (warm)": 89,
}


def instrument_name_to_program(name: str) -> int:
    if name not in GM_PROGRAMS:
        raise KeyError(f"Unknown General MIDI instrument name: {name}")
    return GM_PROGRAMS[name]


def load_midi(path: Union[str, Path]) -> LoadedMidi:
    path = Path(path)
    data = path.read_bytes()
    cursor = 0
    if data[cursor:cursor + 4] != b"MThd":
        raise ValueError("Not a valid MIDI file (missing MThd header)")
    cursor += 4
    header_length = int.from_bytes(data[cursor:cursor + 4], "big")
    cursor += 4
    header_data = data[cursor:cursor + header_length]
    cursor += header_length

    if len(header_data) < 6:
        raise ValueError("Invalid MIDI header")
    _ = int.from_bytes(header_data[0:2], "big")
    num_tracks = int.from_bytes(header_data[2:4], "big")
    ticks_per_quarter = int.from_bytes(header_data[4:6], "big")

    if ticks_per_quarter & 0x8000:
        raise ValueError("SMPTE time code is not supported")

    tempo_us = 500000  # Default 120 BPM
    events: List[Tuple[int, str, Tuple[int, ...]]] = []

    for _ in range(num_tracks):
        if data[cursor:cursor + 4] != b"MTrk":
            raise ValueError("Invalid MIDI track header")
        cursor += 4
        track_length = int.from_bytes(data[cursor:cursor + 4], "big")
        cursor += 4
        track_data = data[cursor:cursor + track_length]
        cursor += track_length
        events.extend(_parse_track(track_data))

    events.sort(key=lambda e: e[0])
    active: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    notes: List[MidiNote] = []

    for tick, kind, payload in events:
        if kind == "tempo" and tempo_us == 500000:
            tempo_us = payload[0]
        elif kind == "note":
            event_type, channel, pitch, velocity = payload
            key = (channel, pitch)
            if event_type == 0x90 and velocity > 0:
                active.setdefault(key, []).append((tick, velocity))
            else:
                starts = active.get(key)
                if starts:
                    start_tick, start_vel = starts.pop()
                    start = _ticks_to_seconds(start_tick, tempo_us, ticks_per_quarter)
                    end = _ticks_to_seconds(tick, tempo_us, ticks_per_quarter)
                    notes.append(
                        MidiNote(pitch=pitch, start=start, end=end, velocity=start_vel)
                    )
        else:
            continue

    tempo_bpm = 60_000_000 / tempo_us
    notes.sort(key=lambda n: (n.start, n.pitch))
    return LoadedMidi(tempo=tempo_bpm, ticks_per_quarter=ticks_per_quarter, notes=notes)


def _parse_track(track_data: bytes) -> List[Tuple[int, str, Tuple[int, ...]]]:
    events: List[Tuple[int, str, Tuple[int, ...]]] = []
    index = 0
    tick = 0
    running_status: Optional[int] = None

    while index < len(track_data):
        delta, index = _read_vlq(track_data, index)
        tick += delta
        if index >= len(track_data):
            break
        status_byte = track_data[index]
        if status_byte & 0x80:
            index += 1
            running_status = status_byte
        elif running_status is not None:
            status_byte = running_status
        else:
            raise ValueError("Running status encountered without previous status byte")

        if status_byte == 0xFF:
            if index >= len(track_data):
                break
            meta_type = track_data[index]
            index += 1
            length, index = _read_vlq(track_data, index)
            meta_data = track_data[index:index + length]
            index += length
            if meta_type == 0x51 and length == 3:
                tempo_us = int.from_bytes(meta_data, "big")
                events.append((tick, "tempo", (tempo_us,)))
            continue
        if status_byte in (0xF0, 0xF7):
            length, index = _read_vlq(track_data, index)
            index += length
            continue

        event_type = status_byte & 0xF0
        channel = status_byte & 0x0F
        if event_type in (0x80, 0x90):
            if index + 2 > len(track_data):
                break
            pitch = track_data[index]
            velocity = track_data[index + 1]
            index += 2
            events.append((tick, "note", (event_type, channel, pitch, velocity)))
        elif event_type == 0xC0:
            if index >= len(track_data):
                break
            program = track_data[index]
            index += 1
            events.append((tick, "program", (channel, program)))
        else:
            param_length = 2 if event_type in (0xA0, 0xB0, 0xE0) else 1
            index += param_length
    return events


def _read_vlq(data: bytes, index: int) -> Tuple[int, int]:
    value = 0
    while index < len(data):
        byte = data[index]
        index += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            break
    return value, index


def _ticks_to_seconds(tick: int, tempo_us: int, ticks_per_quarter: int) -> float:
    seconds_per_tick = tempo_us / 1_000_000.0 / ticks_per_quarter
    return tick * seconds_per_tick


def _seconds_to_ticks(seconds: float, tempo_bpm: float, ticks_per_quarter: int) -> int:
    seconds_per_tick = 60.0 / tempo_bpm / ticks_per_quarter
    return int(round(seconds / seconds_per_tick))


def _encode_midi(midi: SimpleMidiFile) -> bytes:
    ticks = midi.ticks_per_quarter
    header = b"MThd" + (6).to_bytes(4, "big") + (1).to_bytes(2, "big") + (
        (len(midi.instruments) + 1)
    ).to_bytes(2, "big") + ticks.to_bytes(2, "big")

    tempo_us = int(round(60_000_000 / midi.tempo))
    tempo_track = bytearray()
    tempo_track.extend(_encode_vlq(0))
    tempo_track.extend(b"\xFF\x58\x04\x04\x02\x18\x08")  # 4/4
    tempo_track.extend(_encode_vlq(0))
    tempo_track.extend(b"\xFF\x51\x03" + tempo_us.to_bytes(3, "big"))
    tempo_track.extend(b"\x00\xFF\x2F\x00")

    chunks = [header, b"MTrk" + len(tempo_track).to_bytes(4, "big") + tempo_track]

    for instrument in midi.instruments:
        track_bytes = _encode_instrument_track(
            instrument, midi.tempo, midi.ticks_per_quarter
        )
        chunks.append(b"MTrk" + len(track_bytes).to_bytes(4, "big") + track_bytes)

    return b"".join(chunks)


def _encode_instrument_track(instrument: MidiInstrument, tempo_bpm: float, ticks: int) -> bytes:
    events: List[Tuple[int, bytes, int]] = []
    channel = instrument.channel & 0x0F
    program = instrument.program & 0x7F

    events.append((0, bytes([0xC0 | channel, program]), 0))

    for note in instrument.notes:
        start_tick = max(0, _seconds_to_ticks(note.start, tempo_bpm, ticks))
        end_tick = max(start_tick + 1, _seconds_to_ticks(note.end, tempo_bpm, ticks))
        velocity = max(0, min(127, note.velocity))
        events.append((start_tick, bytes([0x90 | channel, note.pitch & 0x7F, velocity]), 1))
        events.append((end_tick, bytes([0x80 | channel, note.pitch & 0x7F, 0]), 2))

    events.sort(key=lambda item: (item[0], item[2]))

    data = bytearray()
    last_tick = 0
    for tick, message, _ in events:
        delta = tick - last_tick
        data.extend(_encode_vlq(delta))
        data.extend(message)
        last_tick = tick
    data.extend(b"\x00\xFF\x2F\x00")
    return bytes(data)


def _encode_vlq(value: int) -> bytes:
    buffer = value & 0x7F
    value >>= 7
    bytes_out = bytearray()
    while value:
        bytes_out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    bytes_out.append(buffer)
    return bytes(bytes_out)
