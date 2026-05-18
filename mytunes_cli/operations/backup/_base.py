from datetime import datetime
from pathlib import Path

from mytunes.annotation import StrippedString
from pydantic import Field

from mytunes_cli.operations._base import SingleLibraryOperation


# noinspection PyAbstractClass
class _BaseOperation(SingleLibraryOperation):
    key: StrippedString | None = Field(
        description="The suffix of the backup filename.",
        default=None,
    )
    path: Path = Field(
        description="The directory of the backup files.",
        default=Path("backups"),
        validation_alias="output",
    )

    @property
    def backup_dir(self) -> Path:
        """The directory of this library's backups."""
        path = self.path
        if not path.is_absolute():
            path = self.state.paths.application / path

        if not path.name == self.library_name:
            path /= self.library_name

        return path

    @property
    def backup_filename(self) -> str:
        """The name of the backup file."""
        timestamp = self.state.timestamp
        return f"{timestamp} ({self.key})" if self.key else timestamp

    @property
    def backup_path(self) -> Path:
        """The full path of the backup file minus the filename extension."""
        return self.backup_dir / self.backup_filename

    @property
    def backup_timestamps(self) -> list[datetime]:
        pattern = "*"
        suffix = ""
        if self.key:
            suffix = f"({self.key})"
            pattern = rf"* {suffix}.*"

        timestamps: list[datetime | None] = []
        for path in self.backup_dir.rglob(pattern):
            filename = path.stem.replace(suffix, "").strip()
            timestamps.append(self.state.parse_datetime(filename))

        return list(filter(None, timestamps))
