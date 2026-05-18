"""
Pretty printers for objects in the CLI.
"""
import functools
import logging
import os
import random
import sys
import traceback
from collections.abc import Sequence, Collection

import pyfiglet
from mytunes import PROGRAM_NAME
from mytunes.logger import Logger
from pydantic import Field
from pydantic_settings import CliSuppress
from rich import get_console
from rich.console import Console

from mytunes_cli._base import BaseSettings
from mytunes_cli.log.settings import LoggingSettings
from mytunes_cli.state import HasGlobalState

# noinspection SpellCheckingInspection
LOGO_FONTS = (
    "basic", "broadway", "chunky", "doom", "drpepper", "epic", "hollywood", "isometric1", "isometric2",
    "isometric3", "isometric4", "larry3d", "shadow", "slant", "speed", "standard", "univers", "whimsy"
)
LOGO_COLOURS = ("red", "yellow", "green", "blue", "cyan", "magenta")


class Printer(HasGlobalState):
    """Handles general printing and logging in support of operations execution."""
    ###########################################################################
    ## Utilities
    ###########################################################################
    @staticmethod
    @functools.wraps(Console.print)
    def print(*args, **kwargs) -> None:
        """Wrapper for rich.print."""
        if not args or not Logger.compact:
            get_console().print(*args, **kwargs)

    @classmethod
    def print_dividing_line(cls, text: str = "", line_char: str = "-") -> None:
        """Print an aligned line with the given text in the centre of the terminal"""
        width = get_console().width

        count_left = ((width - len(text) - 2) // 2)  # -2 for spaces either side of the text
        count_right = count_left + abs(width % 2 - len(text) % 2)  # account for odd numbered widths

        formatted_text = (
             f"[bold cyan]{line_char * count_left}[/] "
             f"[magenta]{text}[/] "
             f"[bold cyan]{line_char * count_right}[/]"
        )

        cls.print()
        cls.print(formatted_text)

    ###########################################################################
    ## Stateless header printers
    ###########################################################################
    @classmethod
    def print_header(cls) -> None:
        """Print header text to the terminal."""
        cls.set_title(PROGRAM_NAME)
        cls.print()
        cls.print_logo()

    @staticmethod
    def set_title(value: str) -> None:
        """Set the terminal title to given ``value``"""
        if sys.platform == "win32":
            os.system(f"title {value}")
        elif sys.platform == "linux":
            os.system(f"echo -n '\033]2;{value}\007'")
        elif sys.platform == "darwin":
            os.system(f"echo '\033]2;{value}\007\\c'")

    @classmethod
    def print_logo(cls, fonts: Sequence[str] = LOGO_FONTS, colours: Collection[str] = LOGO_COLOURS) -> None:
        """Pretty print the logo in the centre of the terminal"""
        width = get_console().width

        colours = list(colours)
        if bool(random.getrandbits(1)):
            colours.reverse()

        font = random.choice(fonts)
        figlet = pyfiglet.Figlet(font=font, direction='left-to-right', justify="left", width=width)

        text = figlet.renderText(PROGRAM_NAME).rstrip().split("\n")
        text_width = max(len(line) for line in text)
        indent = int((width - text_width) / 2)

        for i, line in enumerate(text, random.randint(0, len(colours))):
            line = f"[{colours[i % len(colours)]}]{line} [/]"
            cls.print(f"{' ' * indent}{line}")

    ###########################################################################
    ## Stateful header printers
    ###########################################################################
    def print_sub_header(self) -> None:
        """Print sub-header text to the terminal."""
        self.print_folders()

        if self.state.dry_run:
            self.print_dividing_line("DRY RUN ENABLED", line_char=" ")

    def print_folders(self) -> None:
        """Print the key folder locations to the terminal"""
        self.print()

        file_paths = self._logger.file_paths
        if file_paths:
            self._logger.info(f"[grey74]Logs: {", ".join(map(str, set(file_paths)))}[/]")

        self._logger.info(f"[grey74]App data: {self.state.paths.application}[/]")

    def print_function_header(self, name: str) -> None:
        """Set the terminal title and print the function header to the terminal."""
        title = f"{PROGRAM_NAME}: {name}"
        if self.state.dry_run:
            title += " (DRYRUN)"

        self.set_title(title)
        self.print_dividing_line(name)

    def print_time(self) -> None:
        """Print the time in minutes and seconds in the centre of the terminal"""
        seconds = self.state.time_taken

        mins = int(seconds // 60)
        secs = int(seconds % 60)
        text = f"{mins} mins {secs} secs"

        self.print_dividing_line(text, line_char=" ")
        self._logger.debug(f"Total running time: {round(self.state.time_taken, 3)}s")

    def print_traceback(self, exception: Exception | None = None) -> None:
        """Prints and logs the current traceback."""
        self._logger.debug(traceback.format_exc())
        if any(handler.level <= logging.DEBUG for handler in self._logger.stdout_handlers):
            return

        message = "\n".join(self._extract_exception_messages(exception)).rstrip("\n")
        self.print()
        self.print(f"[red]{message}[/]")

    @classmethod
    def _extract_exception_messages(cls, exc: BaseException | None) -> tuple[str, ...]:
        messages = []

        match exc:
            case None:
                messages.append(traceback.format_exc(0))
            case BaseExceptionGroup():
                # exception group raised when an async operation fails
                # usually the error messages are all the same so this clears up a lot of repeated errors
                group_messages = (m for e in exc.exceptions for m in cls._extract_exception_messages(e))
                messages.extend(m for m in group_messages if m not in messages)
            case _:
                messages.append(str(exc))

        return tuple(messages)

    ###########################################################################
    ## Debug loggers
    ###########################################################################
    def log_global_args(self, args: Sequence[str]) -> None:
        """Logs the raw global args."""
        self._logger.debug(f"Global args: {" ".join(args)}")

    def log_operation_args(self, args: Sequence[str]) -> None:
        """Logs the raw operation args."""
        self._logger.debug(f"Operation args: {" ".join(args)}")

    def log_logging(self, config: LoggingSettings) -> None:
        """Logs the logging config."""
        dump = config.model_dump_yaml(exclude_none=True)
        self._logger.debug(f"Logging config:\n{dump}")

    def log_state(self) -> None:
        """Logs the global state."""
        dump = self.state.model_dump_yaml(exclude_none=True)
        self._logger.debug(f"Global state:\n{dump}")


class HasPrinter(BaseSettings):
    printer: CliSuppress[Printer] = Field(
        description="Printer for headers, footers, and other supporting information",
    )
