"""Entry point: `python -m ffpolicy`."""

import sys


def main() -> int:
    """Dispatch to the GUI, or to the CLI when args are given."""
    if len(sys.argv) > 1:
        from ffpolicy.cli import app as cli_app

        cli_app()
        return 0

    from ffpolicy.gui.main_window import run_gui

    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
