"""Command line interface for the house loop generator."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional

from .generator import HouseLoopOptions, generate_house_loop


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Transform a source MIDI file into an 8-bar house loop with stabs, plucks "
            "and pads."
        )
    )
    parser.add_argument("input", type=Path, help="Path to the source MIDI file")
    parser.add_argument("output", type=Path, help="Where to write the transformed loop")
    parser.add_argument(
        "--mode",
        choices=["auto", "euphoric", "minor_fifth"],
        default="auto",
        help=(
            "Chord flavour to emphasise. 'auto' attempts to detect a mood from the "
            "source material."
        ),
    )
    parser.add_argument(
        "--swing",
        type=float,
        default=0.12,
        help="Swing amount applied to off-beat hits (0-0.4).",
    )
    parser.add_argument(
        "--tempo",
        type=float,
        default=None,
        help="Override tempo in BPM for the generated loop.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for the internal randomiser to create reproducible results.",
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=8,
        help="Number of bars to generate (defaults to 8).",
    )
    return parser


def format_progression(root_names: Iterable[str]) -> str:
    return " - ".join(root_names)


def _pc_to_name(pc: int) -> str:
    return NOTE_NAMES[pc % 12]


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    options = HouseLoopOptions(
        mode=args.mode,
        swing=args.swing,
        seed=args.seed,
        tempo=args.tempo,
        target_bars=args.bars,
    )

    result = generate_house_loop(args.input, options)
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.midi.write(str(output_path))

    chord_summary = format_progression(_pc_to_name(chord.root_pc) for chord in result.chords)
    print("Generated loop info:")
    print(f"  Tempo: {result.tempo:.2f} BPM")
    print(f"  Mode: {result.mode}")
    print(f"  Progression: {chord_summary}")
    print(f"  Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
