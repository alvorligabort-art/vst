# House Loop Maker

This project provides a small executable tool that turns a source MIDI file into an
8 bar house loop. The generator focuses on euphoric house vibes – stabs on the
off-beats, plucky arpeggios and warm pads – while still keeping an emotional
feel. The mood can lean into bright euphoric colours or a darker
"minor/fifth" palette.

## Features

* Analyse an uploaded MIDI file to derive a base chord progression and register.
* Regenerate an 8-bar progression with gentle variations so the loop feels
  fresh but related to the source material.
* Layer three instruments (stabs, plucks and pads) with a swung house rhythm.
* Optional random seed to reproduce the same loop, and a mode switch between
  euphoric and minor/fifth flavours.

## Installation

The tool requires Python 3.10+ and has no runtime dependencies beyond the
standard library. If you wish to run the automated tests, install the packages
listed in `requirements.txt` (currently only `pytest`). A typical setup looks
like:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python -m house_loop_maker <input.mid> <output.mid> [options]
```

Key options:

* `--mode {auto,euphoric,minor_fifth}` – choose the overall chord flavour.
* `--swing` – adjust the swing applied to off-beat hits (0 to 0.4).
* `--tempo` – override the detected tempo.
* `--seed` – fix the random seed for reproducible output.
* `--bars` – number of bars to generate (defaults to 8).

Example:

```bash
python -m house_loop_maker emotional_chords.mid house_loop.mid --mode euphoric --seed 42
```

The command prints a short summary of the generated loop (tempo, chosen mode and
progression) and writes the resulting MIDI file to the requested location.

## Development

Tests live in the `tests/` folder and can be executed with:

```bash
pytest
```

The tests create a temporary MIDI file, run the CLI, and verify the resulting
loop has the expected length and layers.
