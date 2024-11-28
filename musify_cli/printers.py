"""
Pretty printers for objects in the CLI.
"""
import os
import random
import sys
from collections.abc import Sequence, Collection

import pyfiglet
from musify import PROGRAM_NAME

from musify_cli.manager import MusifyProcessor

# noinspection SpellCheckingInspection
LOGO_FONTS = (
    "basic", "broadway", "chunky", "doom", "drpepper", "epic", "hollywood", "isometric1", "isometric2",
    "isometric3", "isometric4", "larry3d", "shadow", "slant", "speed", "standard", "univers", "whimsy"
)
LOGO_COLOURS = (91, 93, 92, 94, 96, 95)


def get_terminal_width() -> int:
    """Get the width in characters of the current terminal"""
    try:
        cols = os.get_terminal_size().columns
    except OSError:
        cols = 120

    return cols


def print_logo(fonts: Sequence[str] = LOGO_FONTS, colours: Collection[int] = LOGO_COLOURS) -> None:
    """Pretty print the Musify logo in the centre of the terminal"""
    colours = list(colours)
    if bool(random.getrandbits(1)):
        colours.reverse()

    cols = get_terminal_width()
    # noinspection SpellCheckingInspection
    figlet = pyfiglet.Figlet(font=random.choice(fonts), direction=0, justify="left", width=cols)

    text = figlet.renderText(PROGRAM_NAME.upper()).rstrip().split("\n")
    text_width = max(len(line) for line in text)
    indent = int((cols - text_width) / 2)

    for i, line in enumerate(text, random.randint(0, len(colours))):
        print(f"{' ' * indent}\33[1;{colours[i % len(colours)]}m{line}\33[0m")
    print()


def print_line(text: str = "", line_char: str = "-") -> None:
    """Print an aligned line with the given text in the centre of the terminal"""
    cols = get_terminal_width()

    text = f" {text} " if text else ""
    amount_left = (cols - len(text)) // 2
    output_len = amount_left * 2 + len(text)
    amount_right = amount_left + (1 if output_len < cols else 0)

    print(f"\33[1;96m{line_char * amount_left}\33[95m{text}\33[1;96m{line_char * amount_right}\33[0m\n")


def print_time(seconds: float) -> None:
    """Print the time in minutes and seconds in the centre of the terminal"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    text = f"{mins} mins {secs} secs"

    cols = get_terminal_width()
    indent = int((cols - len(text)) / 2)

    print(f"\33[1;95m{' ' * indent}{text}\33[0m")


###########################################################################
## Header printers and terminal setters
###########################################################################
def set_title(value: str) -> None:
    """Set the terminal title to given ``value``"""
    if sys.platform == "win32":
        os.system(f"title {value}")
    elif sys.platform == "linux":
        os.system(f"echo -n '\033]2;{value}\007'")
    elif sys.platform == "darwin":
        os.system(f"echo '\033]2;{value}\007\\c'")


def print_header() -> None:
    """Print header text to the terminal."""
    set_title(PROGRAM_NAME)
    print()
    print_logo()


def print_folders(processor: MusifyProcessor) -> None:
    """Print the key folder locations to the terminal"""
    if processor.logger.file_paths:
        processor.logger.info(f"\33[90mLogs: {", ".join(map(str, set(processor.logger.file_paths)))} \33[0m")
    processor.logger.info(f"\33[90mApp data: {processor.paths.base} \33[0m")
    print()


def print_sub_header(processor: MusifyProcessor) -> None:
    """Print sub-header text to the terminal."""
    print_folders(processor)
    if processor.dry_run:
        print_line("DRY RUN ENABLED", " ")


def print_function_header(name: str, processor: MusifyProcessor) -> None:
    """Set the terminal title and print the function header to the terminal."""
    title = f"{PROGRAM_NAME}: {name}"
    if processor.dry_run:
        title += " (DRYRUN)"

    set_title(title)
    print_line(processor.get_func_log_name(name))
