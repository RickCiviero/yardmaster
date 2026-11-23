import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="yardmaster", description="Right job. Right track. Lowest fare.")
    ap.add_argument("--version", action="version", version=f"yardmaster {__version__}")
    try:
        ap.parse_args(argv)
    except SystemExit as e:  # argparse exits on --version/--help/errors; the CLI returns codes instead
        return e.code if isinstance(e.code, int) else 2
    return 0
