"""
Command-line entry point for PyPScan standalone backends.

Usage:
    pypscan --regex PATTERN --base-path PATH --ui tui
    pypscan --regex PATTERN --base-path PATH --ui web [--port 8765]
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="pypscan",
        description="PyPScan — parametric file browser",
    )
    parser.add_argument(
        "--regex", "-r",
        required=True,
        help="Regex with named groups to match file paths (e.g. 'param_(?P<p>.+)/file\\.png')",
    )
    parser.add_argument(
        "--base-path", "-b",
        default="./",
        metavar="PATH",
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--ui", "-u",
        choices=["tui", "web"],
        default="tui",
        help="UI backend: 'tui' (terminal, default) or 'web' (browser)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        metavar="PORT",
        help="Port for the web UI (default: 8765, only used with --ui web)",
    )

    args = parser.parse_args()

    if args.ui == "tui":
        try:
            from .tui import TuiPScan
        except ImportError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        TuiPScan(regex=args.regex, base_path=args.base_path).run()

    elif args.ui == "web":
        try:
            from .web import WebPScan
        except ImportError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        WebPScan(regex=args.regex, base_path=args.base_path, port=args.port).run()


if __name__ == "__main__":
    main()
