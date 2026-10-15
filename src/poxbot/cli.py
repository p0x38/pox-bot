from __future__ import annotations

import argparse

from .config.cli import check_environment, show_config, validate_config
from .main import run
from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='poxbot', description="A Stupid bot's command line interface."
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )

    subparsers = parser.add_subparsers(dest='command')

    run_parser = subparsers.add_parser(
        'run',
        help='Start the bot.',
    )
    run_parser.add_argument(
        '--textual',
        action='store_true',
        help='Render a minimal Textual runtime dashboard for log output.',
    )
    run_parser.set_defaults(func=run)

    doctor_parser = subparsers.add_parser(
        'doctor',
        help='Run diagnostics. (Not implemented)',
    )
    doctor_parser.set_defaults(func=lambda: print('Not implemented'))  # ruff: ignore[print]

    config_parser = subparsers.add_parser(
        'config',
        help='Configuration commands.',
    )

    config_sub = config_parser.add_subparsers(dest='config_command')

    show = config_sub.add_parser(
        'show',
        aliases=['dump'],
        help='Print the current configuration.',
    )
    show.add_argument(
        '--json',
        action='store_true',
        help='Output configuration as JSON.',
    )
    show.set_defaults(func=show_config)

    validate = config_sub.add_parser(
        'validate',
        help='Validate configuration.',
    )
    validate.set_defaults(func=validate_config)

    env_check = config_sub.add_parser(
        'env_check', help='Validate environment variables.'
    )
    env_check.set_defaults(func=check_environment)

    return parser


def main():
    parser = build_parser()
    namespace = parser.parse_args()

    if hasattr(namespace, 'func'):
        namespace.func(namespace)
    else:
        parser.print_help()
