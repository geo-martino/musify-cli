"""
All logging handlers specific to this package.
"""
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from mytunes.processors.time import TimeMapper
from rich.abc import RichRenderable
from rich.logging import RichHandler

if TYPE_CHECKING:
    from mytunes_cli.state import GlobalState


class RenderableHandler(RichHandler):
    def render_message(self, record, message):
        if isinstance(message, RichRenderable):
            return message
        else:
            return super().render_message(record, message)



class FilenameTimedRotatingFileHandler(logging.handlers.BaseRotatingHandler):
    """
    Handles log file and directory rotation based on log file/folder name.

    :param when: The timespan for 'interval' which is used together to calculate the timedelta.
        Accepts same values as :py:class:`TimeMapper`.
    :param interval: The multiplier for ``when``.
        When combined with ``when``, gives the negative timedelta relative to now
        which is the maximum datetime to keep logs for.
    :param count: The maximum number of files to keep.
    :param delay: When True, the file opening is deferred until the first call to emit().
    :param errors: Used to determine how encoding errors are handled.
    """

    def __init__(
            self,
            path: str | Path,
            dt: str | datetime,
            encoding: str | None = None,
            when: str | None = None,
            interval: int | None = None,
            count: int | None = None,
            delay: bool = False,
            errors: str | None = None
    ):
        from mytunes_cli.state import GlobalState  # avoid circular import

        self.dt = dt if isinstance(dt, datetime) else GlobalState.parse_datetime(dt)
        self.delta = TimeMapper(amount=interval, unit=when.lower(), add=False) if when and interval else None
        self.count = count

        path = Path(path).joinpath(f"{dt}.log")
        super().__init__(filename=path, mode="w", encoding=encoding, delay=delay, errors=errors)

        self.rotator()

    def rotator(self):
        """
        Rotates the files in the folder.

        Removes files older than ``self.delta`` and the oldest files when number of files >= count
        until number of files <= count. Current path is excluded from processing.
        """
        folder = Path(self.baseFilename).parent
        if not folder:
            return

        paths = sorted(folder.glob("*"))
        remaining = len(paths)

        for path in paths:
            if path == self.baseFilename:
                continue

            if self._too_old(path) or self._too_many(remaining):
                os.remove(path)
                remaining -= 1

    def _too_many(self, available: int) -> bool:
        # -1 for the yet-to-be-created current file
        return available > (self.count - 1) if self.count is not None else False

    def _too_old(self, path: Path) -> bool:
        from mytunes_cli.state import GlobalState  # avoid circular import
        dt = GlobalState.parse_datetime(path.stem)
        return self.delta is not None and dt < self.delta.apply(self.dt) if dt else False

    # noinspection PyPep8Naming
    @staticmethod
    def shouldRollover(*_, **__) -> bool:
        """Always returns False. Rotation happens on __init__ and only needs to happen once."""
        return False
