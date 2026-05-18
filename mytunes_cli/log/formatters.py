import logging
import os
from copy import copy
from logging import LogRecord

from rich.abc import RichRenderable
from rich.console import Console
from rich.text import Text


class RenderableFormatter(logging.Formatter):
    def format(self, record: LogRecord) -> str | RichRenderable:
        if isinstance(record.msg, RichRenderable):
            return record.msg
        return super().format(record)


class ColourlessFormatter(logging.Formatter):
    def format(self, record: LogRecord) -> str:
        record = copy(record)  # formatter mutates the record so copy is needed

        if isinstance(record.msg, RichRenderable):
            with open(os.devnull, "w") as devnull:
                console = Console(record=True, file=devnull)
                console.print(record.msg)

            record.msg = console.export_text(styles=False).strip()

        record.msg = Text.from_markup(record.getMessage()).plain
        return super().format(record)
