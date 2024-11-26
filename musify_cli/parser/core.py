import logging.config
from pathlib import Path
from typing import Any, Self

from aiorequestful import MODULE_ROOT as AIOREQUESTFUL_ROOT
from musify import MODULE_ROOT as MUSIFY_ROOT
from musify.libraries.local.track.field import LocalTrackField
from musify.logger import MusifyLogger
from musify.processors.filter import FilterComparers
from musify.report import report_missing_tags
from pydantic import BaseModel, Field, DirectoryPath, computed_field

from musify_cli import PACKAGE_ROOT, MODULE_ROOT
from musify_cli.parser.library import LibrariesConfig, APIConfig
from musify_cli.parser.loader import MultiFileLoader
from musify_cli.parser.operations.filters import Filter
from musify_cli.parser.operations.signature import get_default_args
from musify_cli.parser.operations.tags import LOCAL_TRACK_TAG_NAMES, LocalTrackFields
from musify_cli.parser.types import LoadTypesLocal, LoadTypesRemote, EnrichTypesRemote, \
    LoadTypesLocalAnno, LoadTypesRemoteAnno, EnrichTypesRemoteAnno


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

    def model_post_init(self, __context: Any) -> None:
        for formatter in self.formatters.values():  # ensure ANSI colour codes in format are recognised
            if (format_key := "format") in formatter:
                formatter[format_key] = formatter[format_key].replace(r"\33", "\33")

        if self.name and self.name in self.loggers:
            self.configure_additional_loggers(MODULE_ROOT, MUSIFY_ROOT, AIOREQUESTFUL_ROOT)

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


class AppData(BaseModel):
    base: DirectoryPath = Field(
        description="The base directory to use for output data e.g. backups, API tokens, caches etc.",
        default=PACKAGE_ROOT.joinpath("_data"),
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
    local_library: Path = Field(
        description="The directory to use for local library export data. "
                    "May either be a full path or relative path to the 'base'",
        default=Path("library", "local")
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.backup.is_absolute():
            self.backup = DirectoryPath(self.base.joinpath(self.backup))
        if not self.cache.is_absolute():
            self.cache = DirectoryPath(self.base.joinpath(self.cache))
        if not self.token.is_absolute():
            self.token = DirectoryPath(self.base.joinpath(self.token))
        if not self.local_library.is_absolute():
            self.local_library = DirectoryPath(self.base.joinpath(self.local_library))


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


class ReportBase(BaseModel):
    enabled: bool = Field(
        description="When true, trigger this report",
        default=False,
    )
    filter: Filter = Field(
        description="A filter to apply for this report",
        default=FilterComparers(),
    )


class ReportPlaylistDifferences(ReportBase):
    pass


reports_missing_tags_default_args = get_default_args(report_missing_tags)


class ReportMissingTags(ReportBase):
    tags: LocalTrackFields = Field(
        description=f"The tags to check. Accepted tags: {LOCAL_TRACK_TAG_NAMES}",
        default=reports_missing_tags_default_args.get("tags", LocalTrackField.ALL),
    )
    match_all: bool = Field(
        description="When True, consider a track as having missing tags only if it is missing all the given tags",
        default=reports_missing_tags_default_args.get("match_all"),
    )


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
    app_data: AppData = Field(
        description="Configuration for the hierarchy of files needed and/or exported by the program "
                    "e.g. backups, API tokens, caches etc.",
        default=AppData(),
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

    def model_post_init(self, __context: Any) -> None:
        api: APIConfig = self.libraries.remote.api
        if (token_file_path := api.token_file_path) and not token_file_path.is_absolute():
            api.token_file_path = self.app_data.token.joinpath(token_file_path)

        if api.cache.is_local and not (db := Path(api.cache.db)).is_absolute():
            api.cache.db = self.app_data.cache.joinpath(db)

    @classmethod
    def from_file(cls, config_file_path: str | Path) -> tuple[Self, list[Self]]:
        raw_config = MultiFileLoader.load(config_file_path)

        raw_functions_config = raw_config.pop("functions") if "functions" in raw_config else []
        base_config = MusifyConfig(**raw_config)

        return base_config, []
