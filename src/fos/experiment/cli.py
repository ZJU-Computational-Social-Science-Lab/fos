"""
Command-line interface for the checkpointed experiment runner.

Dispatches the init, status, and verify subcommands to their implementations
in commands.py. The run and retry subcommands arrive in a later phase and
are deliberately not wired up yet.

Functions:
    build_parser() — construct the argparse parser with the subcommands
    main()         — parse arguments and run the chosen subcommand
"""

from __future__ import annotations

import argparse

from fos.experiment import commands


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with the init / status / verify subcommands."""
    parser = argparse.ArgumentParser(
        prog="fos.experiment",
        description="Checkpointed runner for the FOS council experiment.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="initialise the state store from run_matrix.csv")
    subparsers.add_parser("status", help="show the run progress summary")
    subparsers.add_parser(
        "verify", help="check that all result files exist and are valid"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse command-line arguments and run the selected subcommand."""
    args = build_parser().parse_args(argv)
    if args.command == "init":
        commands.init()
    elif args.command == "status":
        commands.status()
    elif args.command == "verify":
        commands.verify()
    return 0
