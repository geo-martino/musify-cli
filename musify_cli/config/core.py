import logging.config
import os
import shutil
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Self

from aiorequestful import MODULE_ROOT as AIOREQUESTFUL_ROOT
from musify import MODULE_ROOT as MUSIFY_ROOT
from musify.base import MusifyItem
from musify.libraries.core.collection import MusifyCollection
from musify.libraries.core.object import Playlist
from musify.libraries.local.track.field import LocalTrackField
from musify.logger import MusifyLogger
from musify.processors.filter import FilterComparers
from musify.report import report_missing_tags, report_playlist_differences
from pydantic import BaseModel, Field, DirectoryPath, computed_field, model_validator

from musify_cli import PACKAGE_ROOT, MODULE_ROOT
from musify_cli.config.library import LibrariesConfig
from musify_cli.config.library._core import Runner
from musify_cli.config.library.remote import APIConfig
from musify_cli.config.library.types import LoadTypesLocal, LoadTypesRemote, EnrichTypesRemote, \
    LoadTypesLocalAnno, LoadTypesRemoteAnno, EnrichTypesRemoteAnno
from musify_cli.config.loader import MultiFileLoader
from musify_cli.config.operations.filters import Filter
from musify_cli.config.operations.signature import get_default_args
from musify_cli.config.operations.tags import LOCAL_TRACK_TAG_NAMES, LocalTrackFields


###########################################################################
## Runtime
###########################################################################
class Logging(BaseModel):
    version: int = Field(
        description="Value representing the schema version",
        default=1,
    )
    formatters: dict[str, Any] = Field(
        description="A map of formatter IDs to maps describing how to configure the corresponding Formatter instance",
        default_factory=dict,
    )
    filters: dict[str, Any] = Field(
        description="A map of filter IDs to maps describing how to configure the corresponding Filter instance",
        default_factory=dict,
    )
    handlers: dict[str, Any] = Field(
        description="A map of handler IDs to maps describing how to configure the corresponding Handler instance",
        default_factory=dict,
    )
    loggers: dict[str, Any] = Field(
        description="A map of logger names to maps describing how to configure the corresponding Logger instance",
        default_factory=dict,
    )
    root: dict[str, Any] = Field(
        description="The configuration for the root logger instance",
        default_factory=dict,
    )
    incremental: bool = Field(
        description="Whether the configuration is to be interpreted as incremental to the existing configuration",
        default=False,
    )
    disable_existing_loggers: bool = Field(
        description="Whether any existing non-root loggers are to be disabled",
        default=True,
    )

    name: str | None = Field(
        description="The logger settings to use for this run as found in logging config file",
        default=None
    )
    compact: bool = Field(
        description="Set the logger to compact logging to terminal by removing empty lines",
        default=False,
    )
    bars: bool = Field(
        description="Set the logger to show progress bars for longer operations",
        default=True,
    )

    @computed_field(
        description="The configuration for the selected logger"
    )
    @property
    def logger(self) -> dict[str, Any]:
        """The configuration for the selected logger"""
        return self.loggers.get(self.name, {})

    @model_validator(mode="after")
    def fix_ansi_codes_in_formatters(self) -> Self:
        for formatter in self.formatters.values():  # ensure ANSI colour codes in format are recognised
            if (format_key := "format") in formatter:
                formatter[format_key] = formatter[format_key].replace(r"\33", "\33")

        return self

    @model_validator(mode="after")
    def add_key_loggers(self) -> Self:
        if self.name and self.name in self.loggers:
            self.configure_additional_loggers(MODULE_ROOT, MUSIFY_ROOT, AIOREQUESTFUL_ROOT)
        return self

    def configure_additional_loggers(self, *names: str) -> None:
        """
        Set additional loggers with the given names with the config of the currently selected logger

        :param names: The names of the additional loggers to set.
        """
        for name in names:
            self.loggers[name] = self.logger

    def configure_logging(self) -> None:
        """Configures logging using the currently stored config."""
        MusifyLogger.compact = self.compact
        MusifyLogger.disable_bars = not self.bars

        config_keys = {
            "version", "formatters", "filters", "handlers", "loggers", "root", "incremental", "disable_existing_loggers"
        }
        config = self.model_dump(include=config_keys)

        logging.config.dictConfig(config)

        if self.logger:
            logging.getLogger(MODULE_ROOT).debug(f"Logging config set to: {self.name}")


class Paths(BaseModel):
    base: DirectoryPath = Field(
        description="The base directory to use for output data e.g. backups, API tokens, caches etc.",
        default=PACKAGE_ROOT.joinpath("_data"),
    )
    dt: datetime = Field(
        description="The datetime of the current execution. Used to form execution-specific paths.",
        default=datetime.now()
    )

    backup: Path = Field(
        description="The directory to use for backup output. May either be a full path or relative path to the 'base'",
        default=Path("backup"),
    )
    cache: Path = Field(
        description="The directory to use for cache output. May either be a full path or relative path to the 'base'",
        default=Path("cache"),
    )
    token: Path = Field(
        description="The directory to use for token files. May either be a full path or relative path to the 'base'",
        default=Path("token")
    )
    local_library_exports: Path = Field(
        description="The directory to use for local library export data. "
                    "May either be a full path or relative path to the 'base'",
        default=Path("library", "local")
    )

    @computed_field(
        description="A map of all concrete paths i.e. all paths not including the base path"
    )
    @property
    def _paths(self) -> dict[str, Path]:
        return {
            name: path for name, path in vars(self).items()
            if isinstance(path, Path) and path != self.base
        }

    @computed_field(
        description="The execution time formatted as a string for use in paths"
    )
    @property
    def _dt_as_str(self) -> str:
        return self.dt.strftime("%Y-%m-%d_%H.%M.%S")

    @model_validator(mode="after")
    def join_paths_with_base(self) -> Self:
        for name, path in self._paths.items():
            if not path.is_absolute():
                self.__setattr__(name, DirectoryPath(self.base.joinpath(path)))

        return self

    @model_validator(mode="after")
    def extend_paths_with_execution_time(self) -> Self:
        self.backup = self.backup.joinpath(self._dt_as_str)
        return self

    @model_validator(mode="after")
    def create_directories(self) -> Self:
        if "PYTEST_VERSION" in os.environ:  # don't create directories when executing tests
            return self

        for path in self._paths.values():
            path.mkdir(parents=True, exist_ok=True)
        return self

    def remove_empty_directories(self) -> None:
        """Remove all empty folders."""
        for path in list(self._paths.values()) + [self.base]:
            self._remote_empty_directories_recursively(path)

    def _remote_empty_directories_recursively(self, path: Path) -> None:
        if path.is_dir() and not list(path.glob("*")):
            shutil.rmtree(path)
            self._remote_empty_directories_recursively(path.parent)


###########################################################################
## Pre-/Post- operations
###########################################################################
class ReloadLocal(BaseModel):
    types: LoadTypesLocalAnno = Field(
        description="The types of items/collections to reload for the local library. "
                    f"Accepted types: {[enum.name.lower() for enum in LoadTypesLocal.all()]}",
        default=(),
    )


class ReloadRemoteEnrich(BaseModel):
    enabled: bool = Field(
        description="Enrich the loaded items/collections in this library",
        default=False,
    )
    types: EnrichTypesRemoteAnno = Field(
        description="The types of sub items/collections to enrich for the remote library. "
                    f"Accepted types: {[enum.name.lower() for enum in EnrichTypesRemote.all()]}",
        default=(),
    )


class ReloadRemote(BaseModel):
    types: LoadTypesRemoteAnno = Field(
        description="The types of items/collections to reload for the remote library. "
                    f"Accepted types: {[enum.name.lower() for enum in LoadTypesRemote.all()]}",
        default=(),
    )
    extend: bool = Field(
        description="Extend the remote library with items in the matched items local library",
        default=False,
    )
    enrich: ReloadRemoteEnrich | None = Field(
        description="Configuration for enriching various items/collections in the loaded remote library",
        default=ReloadRemoteEnrich(),
    )


class Reload(BaseModel):
    local: ReloadLocal = Field(
        description="Configuration for reloading various items/collections in the loaded local library",
        default=ReloadLocal(),
    )
    remote: ReloadRemote = Field(
        description="Configuration for reloading various items/collections in the loaded remote library",
        default=ReloadRemote(),
    )


class PrePost(BaseModel):
    filter: Filter = Field(
        description="A generic filter to apply for the current operation. Only used during specific operations.",
        default=FilterComparers(),
    )
    reload: Reload = Field(
        description="Configuration for reloading various items/collections in the loaded libraries",
        default=Reload(),
    )
    pause: str | None = Field(
        description="When provided, pause the operation after this function is complete "
                    "and display the given value as a message in the CLI.",
        default=None,
    )


###########################################################################
## Operations
###########################################################################
class Backup(BaseModel):
    key: str | None = Field(
        description="The key to give to backups",
        default=None
    )


class ReportBase[T](Runner[T]):
    enabled: bool = Field(
        description="When true, trigger this report",
        default=False,
    )
    filter: Filter = Field(
        description="A filter to apply for this report",
        default=FilterComparers(),
    )


class ReportPlaylistDifferences(ReportBase[dict[str, dict[str, tuple[MusifyItem, ...]]]]):
    async def run(self, source: Iterable[Playlist], reference: Iterable[Playlist]):
        if not self.enabled:
            return {}

        return report_playlist_differences(source=self.filter(source), reference=self.filter(reference))


reports_missing_tags_default_args = get_default_args(report_missing_tags)


class ReportMissingTags(ReportBase[dict[str, dict[MusifyItem, tuple[str, ...]]]]):
    tags: LocalTrackFields = Field(
        description=f"The tags to check. Accepted tags: {LOCAL_TRACK_TAG_NAMES}",
        default=reports_missing_tags_default_args.get("tags", LocalTrackField.ALL),
    )
    match_all: bool = Field(
        description="When True, consider a track as having missing tags only if it is missing all the given tags",
        default=reports_missing_tags_default_args.get("match_all"),
    )

    async def run(self, collections: Iterable[MusifyCollection]):
        if not self.enabled:
            return {}

        source = self.filter(collections)
        return report_missing_tags(collections=source, tags=self.tags, match_all=self.match_all)


class Reports(BaseModel):
    playlist_differences: ReportPlaylistDifferences = Field(
        description="Configuration for the playlist differences report",
        default=ReportPlaylistDifferences(),
    )
    missing_tags: ReportMissingTags = Field(
        description="Configuration for the missing tags report",
        default=ReportMissingTags(),
    )


class MusifyConfig(BaseModel):
    libraries: LibrariesConfig = Field(
        description="Configuration for all available libraries",
    )

    # runtime
    execute: bool = Field(
        description="Run all write operations i.e. modify actual data on any write/save/sync commands",
        default=False,
    )
    logging: Logging = Field(
        description="Configuration for the runtime logger",
        default=Logging(),
    )
    paths: Paths = Field(
        description="Configuration for the hierarchy of files needed and/or exported by the program "
                    "e.g. backups, API tokens, caches etc.",
        default=Paths(),
    )
    pre_post: PrePost = Field(
        description="Configuration for pre-/post- operations e.g. reload, pauses, filtering etc.",
        default=PrePost(),
    )

    # operations
    backup: Backup = Field(
        description="Configuration for backup operations",
        default=Backup(),
    )
    reports: Reports = Field(
        description="Configuration for reports operations",
        default=Reports(),
    )

    @model_validator(mode="after")
    def make_api_paths_absolute(self) -> Self:
        api: APIConfig = self.libraries.remote.api
        if (token_file_path := api.token_file_path) and not token_file_path.is_absolute():
            api.token_file_path = self.paths.token.joinpath(token_file_path)

        if api.cache.is_local and not (db := Path(api.cache.db)).is_absolute():
            api.cache.db = self.paths.cache.joinpath(db)

        return self

    @classmethod
    def from_file(cls, config_file_path: str | Path) -> tuple[Self, list[Self]]:
        raw_config = MultiFileLoader.load(config_file_path)

        raw_functions_config = raw_config.pop("functions") if "functions" in raw_config else []
        base_config = MusifyConfig(**raw_config)

        return base_config, []
