from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Annotated, Self, Sequence, Literal

import aiofiles
import yaml
from mytunes.annotation import DEFAULT_IF_NONE
from mytunes.exception import MyTunesValueError, MyTunesValidationError
from mytunes.processors import InputProcessor
from pydantic import Field, model_validator, field_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_settings import CliSuppress

from mytunes_cli.operations._base import LocalLibraryOperation, RemoteLibraryOperation, TagOperation, TAGS_SAVE
from mytunes_cli.operations.backup._base import _BaseOperation
from mytunes_cli.state import GlobalState


# noinspection PyAbstractClass
class _BaseRestore(_BaseOperation, InputProcessor):
    timestamp: Annotated[datetime, DEFAULT_IF_NONE] = Field(
        description=(
            "The timestamp of the backup to restore from. If not provided, the user will be prompted to select "
            "a backup timestamp from the available backups found."
        ),
        default=datetime.min,
    )

    @field_validator("timestamp", mode="before", check_fields=True)
    @classmethod
    def _parse_timestamp[T](cls, value: T | str) -> T | str | datetime:
        if not isinstance(value, str):
            return value
        return GlobalState.parse_datetime(value) or value

    @property
    def backup_filename(self) -> str:
        timestamp = self.state.parse_timestamp(self.timestamp)
        if timestamp is None:
            raise MyTunesValueError(f"Could not parse timestamp: {self.timestamp}")
        return f"{timestamp} ({self.key})" if self.key else timestamp

    @model_validator(mode="after")
    def _validate_backup_dir_exists(self) -> Self:
        if not self.backup_dir.is_dir():
            raise MyTunesValidationError(f"Backup directory {str(self.backup_dir)!r} does not exist.")
        return self

    @model_validator(mode="after")
    def _set_timestamp_from_available(self) -> Self:
        timestamps = sorted(self.backup_timestamps)
        if not timestamps:
            self.__dict__["timestamp"] = datetime.min  # reset timestamp when no backups available
            return self  # handled when the command executes

        if self.timestamp in timestamps:
            return self

        if self.timestamp != datetime.min:
            raise MyTunesValidationError(
                f"Backup {self.backup_filename!r} does not exist for {self.library_name!r}."
            )

        self.__dict__["timestamp"] = self._get_timestamp_from_input(timestamps)
        return self

    def _get_timestamp_from_input(self, timestamps: Sequence[datetime]) -> datetime:
        header = "Available backups"
        if self.key:
            header += f" with key {self.key!r}"

        self._logger.print(f"[blue]{header}[/]", header=2)
        log_groups = "\n".join(
            f"\t- [white]{i}.[/] [blue]{group}[/]"
            for i, group in enumerate(timestamps, 1)
        )
        self._logger.print(log_groups)
        self._logger.print()

        timestamp = None

        while timestamp is None:
            option = self._get_user_input("Select the backup to use")
            
            if option.isdigit() and 0 < int(option) <= len(timestamps):
                timestamp = timestamps[int(option) - 1]
            elif (dt := self.state.parse_datetime(option)) in timestamps:
                timestamp = dt
            else:
                self._logger.print(f"[red]Backup {option!r} not recognised, try again[/]")

        return timestamp

    async def run(self) -> None:
        if self.timestamp == datetime.min or not self.backup_timestamps:
            self._logger.warning("[yellow]No backups found, skipping.[/]")
            return

        await self._restore_library()

        message = f"[green]Successfully restored {self.source} library from {self.backup_filename!r}[/]"
        self._logger.info(message, new_line_start=True)

    @abstractmethod
    async def _restore_library(self) -> None:
        raise NotImplementedError

    async def _load_yaml(self) -> JsonSchemaValue:
        path = Path(str(self.backup_path) + ".yaml")

        async with aiofiles.open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(await file.read())

        self._logger.info(f"Loaded YAML file: [green]{path}[/]", header=2)
        return data


class RestoreLocalLibrary(_BaseRestore, TagOperation, LocalLibraryOperation):
    replace: CliSuppress[Literal[True]] = Field(
        description="Whether to replace existing tags. If False, existing tags will be preserved.",
        default=True,
        init=False,
    )

    async def load(self) -> None:
        log_state = not self.state.get_load_state(self.library.load_tracks)
        await self.library.load_tracks()

        if log_state:
            self.library.log_tracks()

    async def _restore_library(self) -> None:
        await self._restore_tracks()

    async def _restore_tracks(self) -> None:
        self._log_start_tracks()

        dump = await self._load_yaml()

        results = await self.library.restore_tracks(
            dump, include=self.include, exclude=self.exclude, dry_run=self.state.dry_run
        )
        self._log_save_tracks(results, self.library)

    def _log_start_tracks(self) -> None:
        tags = [tag for tag in self.include or TAGS_SAVE if tag not in self.exclude]
        message = (
            f"Restoring {self.source} track tags from backup: "
            f"{self.backup_filename!r} | Tags: {self._logger.format_list_to_string(tags)}"
        )
        self._logger.info(message, header=1, new_line_start=True)


class RestoreRemoteLibrary(_BaseRestore, RemoteLibraryOperation):
    async def _restore_library(self) -> None:
        dump = await self._load_yaml()
        results = await self.library.restore(dump, dry_run=self.state.dry_run)

        self.library.log_sync_results(results)

    def _log_start(self) -> None:
        message = f"Restoring {self.source} library from backup: {self.backup_filename}"
        self._logger.info(message, header=1, new_line_start=True)
