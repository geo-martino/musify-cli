"""
Sets up parser for CLI arguments.
"""
from argparse import ArgumentParser
from pathlib import Path

from musify_cli import PROGRAM_NAME
from musify_cli.config.core import Paths
from musify_cli.manager import MusifyProcessor

PARSER = ArgumentParser(PROGRAM_NAME)

# noinspection PyUnresolvedReferences
PARSER.add_argument(
    "-c", "--config", nargs="?", type=Path,
    default=Paths.model_fields["base"].default.joinpath("config", "config.yml"),
    help="The path to the configuration file for this execution"
)

PROCESSOR_METHOD_NAMES = [
    name.replace("_", "-") for name in MusifyProcessor.__new__(MusifyProcessor).__processormethods__
]

PARSER.add_argument(
    "functions", type=str, nargs="*", default=[],
    choices=PROCESSOR_METHOD_NAMES, help=f"{PROGRAM_NAME} function to run."
)
