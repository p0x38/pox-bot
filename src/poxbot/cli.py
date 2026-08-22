from __future__ import annotations

import argparse

from .main import run
from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="poxbot", description="A Stupid bot's command line interface.")
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    run_parser = subparsers.add_parser(
        "run",
        help="Start the bot.",
    )
    run_parser.add_argument(
        "--textual",
        action="store_true",
        help="Render a minimal Textual runtime dashboard for log output.",
    )
    run_parser.set_defaults(func=run)
    
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Run diagnostics.",
    )
    doctor_parser.set_defaults(func=lambda: print("Not implemented"))
    
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration commands.",
    )
    
    config_sub = config_parser.add_subparsers(dest="config_command")
    
    dump = config_sub.add_parser(
        "dump",
        help="Print configuration.",
    )
    dump.set_defaults(func=lambda: print("Not implemented"))

    validate = config_sub.add_parser(
        "validate",
        help="Validate configuration.",
    )
    validate.set_defaults(func=lambda: print("Not implemented."))
    
    return parser


def main():
    parser = build_parser()
    namespace = parser.parse_args()
    
    if hasattr(namespace, "func"):
        namespace.func(namespace)
    else:
        parser.print_help()
