import logging.config
from collections.abc import Mapping, Sequence, MutableMapping, Callable
from contextlib import suppress
from datetime import datetime
from functools import cached_property
from logging import Handler
from pathlib import Path
from time import perf_counter
from typing import Annotated, ClassVar, Self, Any

from mytunes.annotation import Library
from mytunes.core.library import RemoteLibrary, RemoteMutableLibrary
from mytunes.core.properties.logger import HasLogger
from mytunes.exception import MyTunesKeyError, MyTunesTypeError
from mytunes.local.library import LocalLibrary
from mytunes.logger import Logger
from pydantic import Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict, CliSuppress, CliSettingsSource

from mytunes_cli._base import BaseSettings
from mytunes_cli.log import DT_FORMAT
from mytunes_cli.log.handlers import FilenameTimedRotatingFileHandler
from mytunes_cli.log.settings import LoggingSettings
from mytunes_cli.state._decorators import load_state, save_state
from mytunes_cli.state.paths import GlobalPaths

_TIMESTAMP_FILE_HANDLERS: tuple[type[Handler]] = (
    FilenameTimedRotatingFileHandler,
)


class GlobalState(BaseSettings):
    _default_filename: ClassVar[str] = "settings"
    _supported_extensions: ClassVar[tuple[str, ...]] = ("yaml", "yml")

    model_config = SettingsConfigDict(
        frozen=True,
        extra="ignore",
    )

    paths: GlobalPaths = Field(
        description="The directories to use for application files.",
        default_factory=GlobalPaths,
    )

    libraries: CliSuppress[
        Annotated[
            Mapping[str, Library],
            Field(
                description="A mapping of library names to libraries.",
                default_factory=dict
            )
        ]
    ]

    dry_run: bool = Field(
        description=(
            "Whether to execute all operations without modifying any data. "
            "Data will still be loaded and processed as usual, but any write/save/modify operations will not not "
            "modify data on any system. Results of any operation should still return as usual so "
            "that you can check what would have changed."
        ),
        default=False,
    )

    dt: CliSuppress[datetime] = Field(
        description="The datetime of this run.",
        default=datetime.now(),
        frozen=True,
        init=False,
    )

    @cached_property
    def timestamp(self) -> str:
        """The timestamp of the current run."""
        return self.parse_timestamp(self.dt)

    _start_time = PrivateAttr(default=perf_counter())

    @property
    def time_taken(self) -> float:
        """The amount of time in seconds taken to run the application so far."""
        return perf_counter() - self._start_time

    # TODO: review this on aiorequestful v2
    @model_validator(mode="before")
    @classmethod
    def _set_api_paths[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        """
        This is pretty hacky.

        This makes any relative paths in the API config of libraries absolute to the global paths.
        The challenge is that we have to do this before the APIs are created because some models obscure the path
        used meaning it can't be updated after instantiation. Mostly this affects SQLiteCache at present.

        This should probably be modified/dropped on aiorequestful v2.
        """
        paths = GlobalPaths.model_validate(cls._get_value_from_data(data, "paths"))

        with paths:
            for name, library in cls._get_value_from_data(data, "libraries").items():
                if not isinstance(library, MutableMapping) or (api := library.get("api", {})) is None:
                    continue

                if api.get(key := "token_file_path") is not None and not Path(api[key]).is_absolute():
                    path = api.pop(key, None)
                    api[key] = paths.token.joinpath(path)

                cache = api.get("cache", {})
                if cache.get(key := "path") is not None and not Path(cache[key]).is_absolute():
                    path = cache.pop(key, None)
                    cache[key] = paths.cache.joinpath(path)

        return data

    @field_validator("libraries", mode="after", check_fields=True)
    @classmethod
    def _set_local_states[T: Mapping[str, Library]](cls, libraries: T) -> T:
        """Decorates the local libraries to add state management."""
        for library in libraries.values():
            if not isinstance(library, LocalLibrary):
                continue

            load_tracks = load_state(library.load_tracks)
            load_playlists = load_state(library.load_playlists, required_states=load_tracks)
            load_all = load_state(library.load, set_states=(load_tracks, load_playlists))

            save_tracks = save_state(library.save_tracks, reset_states=load_tracks)
            save_playlists = save_state(library.save_playlists, reset_states=load_playlists)

            library.__dict__["load"] = load_all
            library.__dict__["load_tracks"] = load_tracks
            library.__dict__["load_playlists"] = load_playlists

            library.__dict__["save_tracks"] = save_tracks
            library.__dict__["save_playlists"] = save_playlists

        return libraries

    @field_validator("libraries", mode="after", check_fields=True)
    @classmethod
    def _set_remote_states[T: Mapping[str, Library]](cls, libraries: T) -> T:
        """Decorates the remote libraries to add state management."""
        for library in libraries.values():
            if not isinstance(library, RemoteLibrary):
                continue

            library: RemoteLibrary

            load_tracks = load_state(library.load_tracks)
            load_albums = load_state(library.load_library_albums)
            load_album_tracks = load_state(library.load_library_album_tracks, required_states=load_albums)
            load_artists = load_state(library.load_library_artists)
            load_artist_albums = load_state(library.load_library_artist_albums, required_states=load_artists)
            load_playlists = load_state(library.load_playlists)
            load_playlist_items = load_state(library.load_playlist_items, required_states=load_playlists)

            all_load_states = [
                load_tracks,
                load_albums,
                load_album_tracks,
                load_artists,
                load_artist_albums,
                load_playlists,
                load_playlist_items
            ]
            load_all = load_state(library.load, set_states=all_load_states)

            library.__dict__["load"] = load_all
            library.__dict__["load_tracks"] = load_tracks
            library.__dict__["load_library_albums"] = load_albums
            library.__dict__["load_library_album_tracks"] = load_album_tracks
            library.__dict__["load_library_artists"] = load_artists
            library.__dict__["load_library_artist_albums"] = load_artist_albums
            library.__dict__["load_playlists"] = load_playlists
            library.__dict__["load_playlist_items"] = load_playlist_items

            if not isinstance(library, RemoteMutableLibrary):
                continue

            library: RemoteMutableLibrary

            sync_tracks = save_state(library.sync_tracks, reset_states=load_tracks)
            sync_albums = save_state(library.sync_albums, reset_states=(load_albums, load_album_tracks))
            sync_artists = save_state(library.sync_artists, reset_states=(load_artists, load_artist_albums))
            sync_playlists = save_state(library.sync_playlists, reset_states=(load_playlists, load_playlist_items))
            sync_all = save_state(library.sync, reset_states=all_load_states)

            library.__dict__["sync"] = sync_all
            library.__dict__["sync_tracks"] = sync_tracks
            library.__dict__["sync_albums"] = sync_albums
            library.__dict__["sync_artists"] = sync_artists
            library.__dict__["sync_playlists"] = sync_playlists

            restore_tracks = save_state(library.restore_tracks, reset_states=load_tracks)
            restore_albums = save_state(library.restore_albums, reset_states=(load_albums, load_album_tracks))
            restore_artists = save_state(library.restore_artists, reset_states=(load_artists, load_artist_albums))
            restore_playlists = save_state(
                library.restore_playlists, reset_states=(load_playlists, load_playlist_items)
            )
            restore_all = save_state(library.restore, reset_states=all_load_states)

            library.__dict__["restore"] = restore_all
            library.__dict__["restore_tracks"] = restore_tracks
            library.__dict__["restore_albums"] = restore_albums
            library.__dict__["restore_artists"] = restore_artists
            library.__dict__["restore_playlists"] = restore_playlists

        return libraries

    ###########################################################################
    ## Getter utilites
    ###########################################################################
    def get_library(self, name: str) -> Library:
        """Get library by name."""
        if name not in self.libraries:
            raise MyTunesKeyError(f"Library {name!r} not found.")
        return self.libraries[name]

    def get_local_library(self, name: str) -> LocalLibrary:
        """Get local library by name."""
        library = self.get_library(name)
        if not isinstance(library, LocalLibrary):
            raise MyTunesTypeError(f"Library {name!r} is not a local library: {type(library).__name__!r}")
        return library

    def get_remote_library(self, name: str) -> RemoteLibrary:
        """Get remote library by name."""
        library = self.get_library(name)
        if not isinstance(library, RemoteLibrary):
            raise MyTunesTypeError(f"Library {name!r} is not a remote library: {type(library).__name__!r}")
        return library

    def get_mutable_remote_library(self, name: str) -> RemoteMutableLibrary:
        """Get remote library by name."""
        library = self.get_library(name)
        if not isinstance(library, RemoteMutableLibrary):
            raise MyTunesTypeError(f"Library {name!r} is not a mutable remote library: {type(library).__name__!r}")
        return library

    @staticmethod
    def get_load_state(func: Callable) -> bool:
        return func.loaded if isinstance(func, load_state) else False

    # TODO: test me
    @staticmethod
    def set_load_state(source: Callable, target: Callable) -> None:
        if not isinstance(source, load_state):
            raise MyTunesTypeError(f"Cannot set load state from the given func: {type(source).__name__!r}")
        if not isinstance(target, load_state):
            raise MyTunesTypeError(f"Cannot set load state for the given func: {type(target).__name__!r}")

        target.loaded = source.loaded
        target.result = source.result

    ###########################################################################
    ## Parsers
    ###########################################################################
    @classmethod
    def parse_state(cls, args: Sequence[str]) -> Self:
        """Parse the global state config."""
        # WORKAROUND: we first parse the cli args to get the config path,
        #  then we revalidate using the config path to get the rest of the settings from a config file, if available.
        source = CliSettingsSource(cls, cli_parse_args=list(args), cli_ignore_unknown_args=False)
        parsed = source()

        state = cls(**parsed)
        with state.paths:  # we enter context to format the absolute paths
            state = cls(config_path=state.paths.config, **parsed)

        return state

    def parse_logging_config(self) -> LoggingSettings:
        """Parse the logging config."""
        config = LoggingSettings(config_path=self.paths.config)

        state_handler_names = {kls.__module__ + "." + kls.__name__ for kls in _TIMESTAMP_FILE_HANDLERS}
        for handler in config.handlers.values():
            if handler.class_ in state_handler_names:
                handler.path = str(self.paths.logs)
                handler.dt = self.timestamp

        logging.config.dictConfig(config.model_dump())
        Logger.compact = config.compact

        return config

    @staticmethod
    def parse_datetime(timestamp: str) -> datetime | None:
        """Parse the datetime from the timestamp."""
        with suppress(ValueError):
            return datetime.strptime(timestamp, DT_FORMAT)
        with suppress(ValueError):
            return datetime.fromisoformat(timestamp)
        return None

    @staticmethod
    def parse_timestamp(dt: datetime) -> str | None:
        """Parse the timestamp from the datetime."""
        with suppress(ValueError):
            return dt.strftime(DT_FORMAT)
        return None


class HasGlobalState(BaseSettings, HasLogger):
    state: CliSuppress[GlobalState] = Field(
        description="The application settings.",
        repr=False,
        exclude=True,
    )
