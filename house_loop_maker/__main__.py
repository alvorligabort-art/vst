"""Entry point for ``python -m house_loop_maker``."""
from __future__ import annotations

import sys

from .cli import main as cli_main


def main() -> int:
    """Dispatch to the CLI or GUI depending on the provided arguments."""

    if len(sys.argv) == 1 or sys.argv[1] == "--gui":
        if len(sys.argv) > 1:
            del sys.argv[1]
        from .gui import run

        run()
        return 0

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
