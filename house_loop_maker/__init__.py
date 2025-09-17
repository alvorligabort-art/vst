"""Tools for turning source MIDI files into euphoric house loops."""

from .generator import HouseLoopOptions, HouseLoopResult, generate_house_loop

__all__ = ["HouseLoopOptions", "HouseLoopResult", "generate_house_loop", "run_gui"]


def run_gui() -> None:
    """Launch the graphical interface."""
    from .gui import run_gui as _run_gui

    _run_gui()
