"""
All logging handlers specific to this package.
"""
import logging.handlers
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from musify.processors.time import TimeMapper

from musify_cli.log import LOGGING_DT_FORMAT


class CurrentTimeRotatingFileHandler(logging.handlers.BaseRotatingHandler):
    """
    Handles log file and directory rotation based on log file/folder name.

    :param filename: The full path to the log file.
        Optionally, include a '{}' part in the path to format in the given execution time.
        When None, defaults to '{}.log'
    :param dt: The execution time of the program to use when building the full path to the log file.
    :param when: The timespan for 'interval' which is used together to calculate the timedelta.
        Accepts same values as :py:class:`TimeMapper`.
    :param interval: The multiplier for ``when``.
        When combined with ``when``, gives the negative timedelta relative to now
        which is the maximum datetime to keep logs for.
    :param count: The maximum number of files to keep.
    :param delay: When True, the file opening is deferred until the first call to emit().
    :param errors: Used to determine how encoding errors are handled.
    """

    __slots__ = ("dt", "filename", "delta", "count", "removed")

    def __init__(
            self,
            filename: str | Path | None = None,
            encoding: str | None = None,
            dt: datetime | None = None,
            when: str | None = None,
            interval: int | None = None,
            count: int | None = None,
            delay: bool = False,
            errors: str | None = None
    ):
        self.dt = dt if dt is not None else datetime.now()
        if not filename:
            filename = "{}.log"

        if "{}" in str(filename):
            dt_str = self.dt.strftime(LOGGING_DT_FORMAT)
            self.filename = Path(str(filename).format(dt_str))
        else:
            self.filename = Path(filename)

        self.filename.parent.mkdir(parents=True, exist_ok=True)

        self.delta = TimeMapper(when.lower())(interval) if when and interval else None
        self.count = count

        self.removed: list[datetime] = []  # datetime on the files that were removed
        self.rotator(unformatted=str(filename), formatted=self.filename)

        if "PYTEST_VERSION" in os.environ:  # don't create log file when executing tests
            filename = Path(tempfile.gettempdir(), self.filename)
        else:
            filename = self.filename

        super().__init__(filename=filename, mode="w", encoding=encoding, delay=delay, errors=errors)

    # noinspection PyPep8Naming
    @staticmethod
    def shouldRollover(*_, **__) -> bool:
        """Always returns False. Rotation happens on __init__ and only needs to happen once."""
        return False

    def rotator(self, unformatted: str, formatted: str | Path):
        """
        Rotates the files in the folder on the given ``unformatted`` path.
        Removes files older than ``self.delta`` and the oldest files when number of files >= count
        until number of files <= count. ``formatted`` path is excluded from processing.
        """
        formatted = Path(formatted)
        folder = formatted.parent
        if not folder:
            return

        # get current files present and prefix+suffix to remove when processing
        paths = tuple(f for f in list(folder.glob("*")) if f != formatted)
        prefix = unformatted.split("{")[0] if "{" in unformatted and "}" in unformatted else ""
        suffix = unformatted.split("}")[1] if "{" in unformatted and "}" in unformatted else ""

        remaining = len(paths)
        for path in sorted(paths):
            too_many = self.count is not None and remaining >= (self.count - 1)  # -1 for current file/folder

            dt_part = str(path).removeprefix(prefix).removesuffix(suffix)
            try:
                dt_file = datetime.strptime(dt_part, LOGGING_DT_FORMAT)
                too_old = self.delta is not None and dt_file < self.dt - self.delta
            except ValueError:
                dt_file = None
                too_old = False

            is_empty = path.is_dir() and not list(path.glob("*"))

            if too_many or too_old or is_empty:
                os.remove(path) if path.is_file() else shutil.rmtree(path)
                remaining -= 1

                if dt_file and dt_file not in self.removed:
                    self.removed.append(dt_file)
