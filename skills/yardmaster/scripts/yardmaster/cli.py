import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="yardmaster", description="Right job. Right track. Lowest fare.")
    ap.add_argument("--version", action="version", version=f"yardmaster {__version__}")
    ap.parse_args(argv)
    return 0
