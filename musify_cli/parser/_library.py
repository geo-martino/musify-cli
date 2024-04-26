"""
Sets up and configures the parser for all arguments relating to :py:class:`Library` objects
and their related objects/configuration.
"""
import argparse
import sys
from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Self

from jsonargparse import ArgumentParser, ActionParser
from jsonargparse.typing import Path_dw, Path_fc
from musify.file.path_mapper import PathStemMapper
from musify.libraries.local.library import LocalLibrary, LIBRARY_CLASSES
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote import REMOTE_SOURCES
from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.object import RemotePlaylist
from musify.libraries.remote.core.processors.check import RemoteItemChecker
from musify.libraries.remote.core.processors.search import RemoteItemSearcher
from musify.libraries.remote.spotify import SOURCE_NAME as SPOTIFY_SOURCE
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.processors.filter import FilterComparers
from musify.utils import to_collection

from musify_cli.parser._utils import EpilogHelpFormatter, LOCAL_TRACK_TAG_NAMES, MultiType
from musify_cli.parser._utils import get_default_args, get_tags, get_comparers_filter
from musify_cli.exception import ParserError

LOCAL_LIBRARY_TYPES = [cls.source.lower() for cls in LIBRARY_CLASSES]
REMOTE_LIBRARY_TYPES = [source.casefold() for source in REMOTE_SOURCES]


###########################################################################
## Local
###########################################################################
## Paths parsers
class LocalLibraryPathsParser[T: Any](ABC):
    """Base class for parsing and validating library paths config, giving platform appropriate paths."""

    @property
    def _platform_key(self) -> str:
        platform_map = {"win32": "win", "linux": "lin", "darwin": "mac"}
        return platform_map[sys.platform]

    @property
    def paths(self) -> T:
        """The path/s configured for the current platform"""
        return self.__getattribute__(self._platform_key)

    @classmethod
    @abstractmethod
    def parse_config(cls, config: MultiType[str] | Self) -> T:
        """Parse and validate given ``config`` and return the platform appropriate path/s"""
        raise NotImplementedError

    def validate(self) -> None:
        """Validate the current settings"""
        if not self.paths:
            raise ParserError("No paths given for the current platform", key=self._platform_key)

    def as_dict(self) -> dict[str, T]:
        """Return the attributes of this dataclass as a dictionary."""
        return {key: self.__getattribute__(key) for key in self.__annotations__}


@dataclass(frozen=True)
class LocalLibraryPaths[T: Collection[str]](LocalLibraryPathsParser):
    """Parses and validates library paths for a :py:class:`LocalLibrary`, giving platform appropriate paths."""

    win: T = ()
    lin: T = ()
    mac: T = ()

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def _platform_key(cls) -> str:
        platform_map = {"win32": "win", "linux": "lin", "darwin": "mac"}
        return platform_map[sys.platform]

    @classmethod
    def parse_config(cls, config: MultiType[str]):
        kwargs = {}
        if isinstance(config, Mapping):
            for key in set(cls.__annotations__).intersection(key.casefold() for key in config):
                value = config[key.casefold()]
                if isinstance(value, str):
                    kwargs[key] = (value,)
                elif isinstance(value, Collection):
                    kwargs[key] = tuple(value)
        elif isinstance(config, str):
            kwargs[cls._platform_key] = to_collection(config)
        elif isinstance(config, Collection):
            kwargs[cls._platform_key] = config

        parsed = cls(**kwargs)
        parsed.validate()
        return parsed.paths


@dataclass(frozen=True)
class MusicBeePaths[T: str | None](LocalLibraryPaths):
    """Parses and validates library paths for a :py:class:`MusicBee` library, giving platform appropriate paths."""

    win: T = None
    lin: T = None
    mac: T = None

    @classmethod
    def parse_config(cls, config: MultiType[str]):
        kwargs = {}
        if isinstance(config, Mapping):
            for key in set(cls.__annotations__).intersection(key.casefold() for key in config):
                value = config[key.casefold()]
                if isinstance(value, str):
                    kwargs[key] = value
                elif isinstance(value, Collection):
                    kwargs[key] = next(iter(value), None)
        elif isinstance(config, str):
            kwargs[cls._platform_key] = config
        elif isinstance(config, Collection):
            kwargs[cls._platform_key] = next(iter(config), None)

        parsed = cls(**kwargs)
        parsed.validate()
        return parsed.paths

    def validate(self) -> None:
        super().validate()
        if not isinstance(self.paths, str):
            raise ParserError(
                "Path is not a string. Something is wrong, this shouldn't have happened.", value=self.paths,
            )


## Arguments builders
def extend_local_paths_arguments(paths: ArgumentParser) -> None:
    """Extend the given ``paths`` parser with generic arguments."""
    # TODO: this should also include other platform re-mappings from the 'library' paths key
    paths.add_argument(
        "--map", type=dict, required=False, default=get_default_args(PathStemMapper).get("stem_map"),
        help="A map of stems to be used as part of the PathStemMapper"
    )


def add_local_playlists_arguments(core: ArgumentParser, source: str) -> None:
    """Create and add generic local playlists arguments to the given ``core`` parser."""
    group = core.add_argument_group(
        title=f"{source} playlists options",
        description=f"Configure the handling of playlists for this {source} library",
    )
    playlists = ArgumentParser(prog=f"{source} playlists", formatter_class=EpilogHelpFormatter)

    playlists.add_argument(
        "--filter", type=get_comparers_filter, default=FilterComparers(),
        help="The filter to apply to available playlists. Filters on playlist names."
    )

    group.add_argument("--playlists", action=ActionParser(playlists))


def add_local_updater_arguments(core: ArgumentParser) -> None:
    """Create and add arguments for the :py:meth:`LocalTrack.save` method to the given ``core`` parser."""
    update_tags_group = core.add_argument_group(
        title="Update tags options",
        description="Options for tag update operations"
    )
    update_tags = ArgumentParser(prog="Update tags", formatter_class=EpilogHelpFormatter)

    update_tags.add_argument(
        "--tags", type=get_tags, default=get_default_args(LocalTrack.save).get("tags", LocalTrackField.ALL),
        help=f"The tags to be updated. Accepted tags: {LOCAL_TRACK_TAG_NAMES}"
    )
    update_tags.add_method_arguments(
        LocalTrack, "save", as_group=False, skip={"tags", "dry_run"}
    )

    update_tags_group.add_argument("--updater", action=ActionParser(update_tags))


## LocalLibrary
local_library = ArgumentParser(
    prog="Local library",
    formatter_class=EpilogHelpFormatter,
    add_help=False,
    usage=argparse.SUPPRESS
)

local_library_paths_group = local_library.add_argument_group(
    title="Paths",
    description="Set the paths options for this local library"
)
local_library_paths = ArgumentParser(prog="Local library paths", formatter_class=EpilogHelpFormatter)

local_library_paths.add_argument(
    "--library", type=LocalLibraryPaths.parse_config, required=True,
    help="The paths for the library. May be defined as a string, list of strings, "
         "or a map with platform specific keys relating to the library paths for that platform. "
         f"Recognised platform keys: {tuple(LocalLibraryPaths.__annotations__)}"
)
local_library_paths.add_argument(
    "--playlists", type=Path_dw, default=get_default_args(LocalLibrary).get("playlist_folder"),
    help="The path of the playlist folder."
)
extend_local_paths_arguments(local_library_paths)
local_library_paths_group.add_argument("--paths", action=ActionParser(local_library_paths))

add_local_playlists_arguments(local_library, "Local")
add_local_updater_arguments(local_library)

## MusicBee
musicbee = ArgumentParser(
    prog="MusicBee library",
    formatter_class=EpilogHelpFormatter,
    add_help=False,
    usage=argparse.SUPPRESS
)

musicbee_paths_group = musicbee.add_argument_group(
    title="Paths",
    description="Set the paths options for this MusicBee library"
)
musicbee_paths = ArgumentParser(prog="MusicBee library paths", formatter_class=EpilogHelpFormatter)

musicbee_paths.add_argument(
    "--library", type=MusicBeePaths.parse_config, required=True,
    help="The path for the MusicBee library folder. May be defined as a string "
         "or a map with platform specific keys relating to the MusicBee library folder for that platform. "
         f"Recognised platform keys: {tuple(MusicBeePaths.__annotations__)}"
)
extend_local_paths_arguments(musicbee_paths)
musicbee_paths_group.add_argument("--paths", action=ActionParser(musicbee_paths))

add_local_playlists_arguments(musicbee, "MusicBee")
add_local_updater_arguments(musicbee)


###########################################################################
## Libraries - Remote
###########################################################################
## Arguments builders
def add_remote_api_arguments(core: ArgumentParser, source: str, api: type[RemoteAPI]) -> None:
    """
    Create and add arguments for creating the given ``api`` for a certain ``source``
    to the given ``core`` parser.
    """
    group = core.add_argument_group(
        title=f"{source} API options",
        description=f"Configure the API for this {source} library",
    )
    remote_api = ArgumentParser(prog=f"{source} API", formatter_class=EpilogHelpFormatter)

    remote_api.add_class_arguments(api, as_group=False)
    remote_api.add_argument(
        "--token-path", type=str | Path_fc,  # type switched to Path_fc when linked to main config
        help="Path to use for loading and saving a token."
    )
    remote_api.add_argument(
        "--cache-path", type=str | Path_fc,  # type switched to Path_fc when linked to main config
        help="Path to use to store the requests session's sqlite cache."
    )
    remote_api.add_argument(
        "--use-cache", type=bool, default=False,
        help="Use the cache when calling the API endpoint. "
             "When using a CachedSession, set as False to refresh the cached response."
    )

    group.add_argument("--api", action=ActionParser(remote_api))


def add_remote_playlists_arguments(core: ArgumentParser, source: str) -> None:
    """
    Create and add arguments for managing remote playlists for a certain ``source``
    to the given ``core`` parser.
    """
    group = core.add_argument_group(
        title=f"{source} playlists options",
        description=f"Configure the handling of playlists for this {source} library",
    )
    remote_playlists = ArgumentParser(prog=f"{source} playlists", formatter_class=EpilogHelpFormatter)

    remote_playlists.add_argument(
        "--filter", type=get_comparers_filter, default=FilterComparers(),
        help="The filter to apply to available playlists. Filters on playlist names."
    )

    def _tag_filter_is_valid(config: dict[str, Any]) -> dict[str, Any]:
        config = dict(config)
        for tag, value in config.items():
            if tag not in LOCAL_TRACK_TAG_NAMES:
                raise ParserError(f"Unrecognised {tag=}", key="playlists.sync.filter")
            if not value:
                raise ParserError(f"No value given for {tag=}", key="playlists.sync.filter")

            config[tag] = tuple(str(v) for v in to_collection(value))

        return config

    remote_playlists_sync = ArgumentParser(prog=f"{source} playlists sync", formatter_class=EpilogHelpFormatter)
    remote_playlists_sync.add_method_arguments(
        RemotePlaylist, "sync", as_group=False, skip={"items", "dry_run"}
    )
    remote_playlists_sync.add_argument(
        "--filter", type=_tag_filter_is_valid, default={},
        help="The filter to apply to tracks before running any sync. "
             "Parse a tag names as the key, any item matching the values given for each corresponding "
             "tag will be filtered out of any sync operations. "
             "NOTE: Only `string` value types are currently supported."
             f"Accepted tags: {LOCAL_TRACK_TAG_NAMES}"
    )
    remote_playlists.add_argument("--sync", action=ActionParser(remote_playlists_sync))

    group.add_argument("--playlists", action=ActionParser(remote_playlists))


def add_remote_processor_arguments(core: ArgumentParser, source: str) -> None:
    """
    Create and add arguments for creating remote processors for a certain ``source``
    to the given ``core`` parser.
    """
    group = core.add_argument_group(
        title=f"{source} processor options",
        description=f"Configure the processors for this {source} library",
    )

    group.add_class_arguments(
        RemoteItemChecker, "check", as_group=False,
        skip={"matcher", "object_factory", "use_cache"}
    )
    group.add_class_arguments(
        RemoteItemSearcher, "search", as_group=False,
        skip={"matcher", "object_factory", "use_cache"}
    )


## Spotify
spotify = ArgumentParser(
    prog="Spotify library",
    formatter_class=EpilogHelpFormatter,
    add_help=False,
    usage=argparse.SUPPRESS
)
add_remote_api_arguments(spotify, source=SPOTIFY_SOURCE, api=SpotifyAPI)
add_remote_playlists_arguments(spotify, source=SPOTIFY_SOURCE)
add_remote_processor_arguments(spotify, source=SPOTIFY_SOURCE)

###########################################################################
## Main parser
###########################################################################
LIBRARY_PARSER = ArgumentParser(
    prog="Library",
    formatter_class=EpilogHelpFormatter,
    add_help=False,
    usage=argparse.SUPPRESS
)
LIBRARY_PARSER.add_argument(
    "-n", "--name", type=str, required=True,
    help="The user-assigned name of this library",
)
library_sub = LIBRARY_PARSER.add_subcommands(dest="type", required=True, description=None)
library_sub_map = {
    "Local": local_library,
    "MusicBee": musicbee,
    "Spotify": spotify,
}
for command, sub_parser in library_sub_map.items():
    library_sub.add_subcommand(command.lower(), sub_parser)


###########################################################################
## Epilog for core parser
###########################################################################
LIBRARY_EPILOG_LINES = [
    "The following settings relate to each library type.\n"
    "Set these options in your config file to use as part of the library options as required.",
    "",
    "Core options:",
    "",
    "\t" + LIBRARY_PARSER.format_help().replace("\n", "\n\t\t")
]

for command, sub_parser in library_sub_map.items():
    LIBRARY_EPILOG_LINES.extend([
        f"{command} library options:",
        "",
        "\t" + sub_parser.format_help().replace("\n", "\n\t\t")
    ])

LIBRARY_EPILOG = "\n" + "\n\t".join(LIBRARY_EPILOG_LINES)