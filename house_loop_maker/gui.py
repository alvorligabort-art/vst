"""Tkinter user interface for the House Loop Maker."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:  # pragma: no cover - handled gracefully at runtime
    raise RuntimeError(
        "Tkinter is required to use the graphical interface. "
        "Please install the Tk libraries for your platform."
    ) from exc

from . import simple_midi
from .generator import HouseLoopOptions, HouseLoopResult, generate_house_loop

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class HouseLoopApp:
    """Main window for the House Loop Maker GUI."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("House Loop Maker")
        self.root.geometry("520x400")
        self.root.minsize(480, 360)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="auto")
        self.swing_var = tk.DoubleVar(value=0.12)
        self.swing_display_var = tk.StringVar(value="Swing: 0.12")
        self.tempo_var = tk.StringVar()
        self.bars_var = tk.StringVar(value="8")
        self.seed_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select a MIDI file to get started.")
        self.summary_var = tk.StringVar(value="")
        self._preview_file: Optional[Path] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        main = ttk.Frame(self.root, padding=16)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)

        # Input MIDI selection
        ttk.Label(main, text="Source MIDI file:").grid(row=0, column=0, sticky="w")
        input_row = ttk.Frame(main)
        input_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        input_row.columnconfigure(0, weight=1)
        input_entry = ttk.Entry(input_row, textvariable=self.input_var)
        input_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(input_row, text="Browse", command=self._choose_input).grid(
            row=0, column=1, padx=(8, 0)
        )

        # Output path selection
        ttk.Label(main, text="Output MIDI file:").grid(row=2, column=0, sticky="w")
        output_row = ttk.Frame(main)
        output_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        output_row.columnconfigure(0, weight=1)
        output_entry = ttk.Entry(output_row, textvariable=self.output_var)
        output_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(output_row, text="Browse", command=self._choose_output).grid(
            row=0, column=1, padx=(8, 0)
        )

        # Options frame
        options = ttk.LabelFrame(main, text="Options", padding=12)
        options.grid(row=4, column=0, columnspan=2, sticky="nsew")
        options.columnconfigure(1, weight=1)

        ttk.Label(options, text="Mood:").grid(row=0, column=0, sticky="w")
        mode_box = ttk.Combobox(
            options,
            textvariable=self.mode_var,
            values=["auto", "euphoric", "minor_fifth"],
            state="readonly",
        )
        mode_box.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        swing_row = ttk.Frame(options)
        swing_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        swing_row.columnconfigure(0, weight=1)
        swing_scale = ttk.Scale(
            swing_row,
            from_=0.0,
            to=0.4,
            orient="horizontal",
            variable=self.swing_var,
            command=self._update_swing_label,
        )
        swing_scale.grid(row=0, column=0, sticky="ew")
        ttk.Label(swing_row, textvariable=self.swing_display_var, width=14).grid(
            row=0, column=1, padx=(8, 0)
        )

        ttk.Label(options, text="Tempo override (BPM):").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(options, textvariable=self.tempo_var).grid(
            row=2, column=1, sticky="ew", pady=(0, 6)
        )

        ttk.Label(options, text="Bars to generate:").grid(row=3, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.bars_var).grid(
            row=3, column=1, sticky="ew", pady=(0, 6)
        )

        ttk.Label(options, text="Random seed:").grid(row=4, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.seed_var).grid(
            row=4, column=1, sticky="ew"
        )

        # Action buttons
        button_row = ttk.Frame(main)
        button_row.grid(row=5, column=0, columnspan=2, pady=(16, 8), sticky="ew")
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)
        button_row.columnconfigure(2, weight=1)

        ttk.Button(button_row, text="Preview", command=self.preview_loop).grid(
            row=0, column=0, padx=4, sticky="ew"
        )
        ttk.Button(button_row, text="Generate", command=self.generate_loop).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ttk.Button(button_row, text="Quit", command=self._on_close).grid(
            row=0, column=2, padx=4, sticky="ew"
        )

        # Summary area
        summary_frame = ttk.LabelFrame(main, text="Latest result", padding=12)
        summary_frame.grid(row=6, column=0, columnspan=2, sticky="nsew")
        summary_frame.columnconfigure(0, weight=1)
        ttk.Label(
            summary_frame, textvariable=self.summary_var, justify="left", wraplength=440
        ).grid(row=0, column=0, sticky="w")

        # Status bar
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            padding=(12, 8),
        )
        status_bar.grid(row=1, column=0, sticky="ew")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _choose_input(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select source MIDI",
            filetypes=[("MIDI Files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if file_path:
            self.input_var.set(file_path)
            if not self.output_var.get():
                suggested = Path(file_path).with_name(
                    Path(file_path).stem + "_loop.mid"
                )
                self.output_var.set(str(suggested))
            self.status_var.set("Ready to generate a loop.")

    def _choose_output(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Save generated MIDI",
            defaultextension=".mid",
            filetypes=[("MIDI Files", "*.mid"), ("All files", "*.*")],
        )
        if file_path:
            self.output_var.set(file_path)

    def _update_swing_label(self, value: str) -> None:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            amount = self.swing_var.get()
        self.swing_display_var.set(f"Swing: {amount:.2f}")

    def _collect_options(self) -> HouseLoopOptions:
        swing = max(0.0, min(0.4, float(self.swing_var.get())))
        tempo_value = self._parse_float(self.tempo_var.get())
        bars_value = self._parse_int(self.bars_var.get(), default=8)
        seed_value = self._parse_int(self.seed_var.get(), allow_negative=False)

        if bars_value <= 0:
            raise ValueError("Number of bars must be greater than zero.")
        if tempo_value is not None and tempo_value <= 0:
            raise ValueError("Tempo override must be a positive number.")

        return HouseLoopOptions(
            mode=self.mode_var.get(),
            swing=swing,
            tempo=tempo_value,
            target_bars=bars_value,
            seed=seed_value,
        )

    def generate_loop(self) -> None:
        input_path = self._validate_input_path()
        if input_path is None:
            return

        output_path = Path(self.output_var.get()).expanduser()
        if not output_path.suffix:
            output_path = output_path.with_suffix(".mid")

        try:
            options = self._collect_options()
            result = generate_house_loop(input_path, options)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result.midi.write(str(output_path))
        except Exception as exc:  # pragma: no cover - GUI feedback
            messagebox.showerror("Generation failed", str(exc))
            self.status_var.set("Generation failed. See message for details.")
            return

        self._show_result(result, output_path)
        messagebox.showinfo(
            "Loop generated",
            f"Saved new loop to\n{output_path}",
        )

    def preview_loop(self) -> None:
        input_path = self._validate_input_path()
        if input_path is None:
            return

        try:
            options = self._collect_options()
            result = generate_house_loop(input_path, options)
            preview_file = self._write_preview_file(result.midi)
        except Exception as exc:  # pragma: no cover - GUI feedback
            messagebox.showerror("Preview failed", str(exc))
            self.status_var.set("Preview failed. See message for details.")
            return

        self._show_result(result, preview_file)
        self._open_file(preview_file)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _show_result(self, result: HouseLoopResult, destination: Path) -> None:
        progression = " → ".join(NOTE_NAMES[chord.root_pc % 12] for chord in result.chords)
        summary = (
            f"File: {destination}\n"
            f"Tempo: {result.tempo:.2f} BPM\n"
            f"Mode: {result.mode}\n"
            f"Progression: {progression}"
        )
        self.summary_var.set(summary)
        self.status_var.set("Loop ready. Use Preview or Generate again if needed.")

    def _validate_input_path(self) -> Optional[Path]:
        path = Path(self.input_var.get()).expanduser()
        if not path.exists():
            messagebox.showwarning(
                "Missing file", "Please choose a valid source MIDI file first."
            )
            return None
        return path

    def _write_preview_file(self, midi_file: simple_midi.SimpleMidiFile) -> Path:
        if self._preview_file and self._preview_file.exists():
            try:
                self._preview_file.unlink()
            except OSError:
                pass
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".mid", prefix="house_loop_preview_"
        ) as tmp:
            temp_path = Path(tmp.name)
        midi_file.write(str(temp_path))
        self._preview_file = temp_path
        return temp_path

    def _open_file(self, path: Path) -> None:
        self.status_var.set(f"Opening preview: {path}")
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
                return
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(path)])
        except Exception:
            messagebox.showinfo(
                "Preview saved",
                f"Preview MIDI saved to:\n{path}\n"
                "Open it in your preferred MIDI player to listen.",
            )

    def _on_close(self) -> None:
        if self._preview_file and self._preview_file.exists():
            try:
                self._preview_file.unlink()
            except OSError:
                pass
        self.root.destroy()

    @staticmethod
    def _parse_float(value: str) -> Optional[float]:
        value = value.strip()
        if not value:
            return None
        return float(value)

    @staticmethod
    def _parse_int(value: str, default: Optional[int] = None, allow_negative: bool = True) -> Optional[int]:
        value = value.strip()
        if not value:
            return default
        parsed = int(value)
        if not allow_negative and parsed < 0:
            raise ValueError("Value must not be negative.")
        return parsed


def run() -> None:
    """Launch the House Loop Maker GUI."""
    root = tk.Tk()
    HouseLoopApp(root)
    root.mainloop()


def run_gui() -> None:
    """Backward compatible wrapper used by :func:`house_loop_maker.run_gui`."""
    run()
