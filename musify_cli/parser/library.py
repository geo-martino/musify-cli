"""
Sets up and configures the parser for all arguments relating to :py:class:`Library` objects
and their related objects/configuration.
"""
import sys
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, MutableMapping
from datetime import timedelta, date, datetime
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import Literal, Any, Self, Type, Annotated

from aiorequestful.cache.backend import CACHE_TYPES, ResponseCache, SQLiteCache
from aiorequestful.timer import GeometricCountTimer, StepCeilingTimer
from aiorequestful.types import UnitSequence
from musify.field import Fields
from musify.libraries.local.library import LIBRARY_CLASSES, LocalLibrary, MusicBee
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote import REMOTE_SOURCES
from musify.libraries.remote.core.object import RemotePlaylist, PLAYLIST_SYNC_KINDS
from musify.libraries.remote.spotify.library import SpotifyLibrary as _SpotifyLibrary
from musify.processors.check import RemoteItemChecker
from musify.processors.download import ItemDownloadHelper
from musify.processors.filter import FilterComparers
from musify.utils import to_collection
from pydantic import BaseModel, DirectoryPath, Field, SecretStr, confloat, NonNegativeFloat, PositiveInt, \
    computed_field, PrivateAttr, BeforeValidator, model_validator, conint

from musify_cli.exception import ParserError
from musify_cli.parser.operations.filters import Filter
from musify_cli.parser.operations.signature import get_default_args, get_arg_descriptions
from musify_cli.parser.operations.tagger import Tagger
from musify_cli.parser.operations.tags import TagFilter, LocalTrackFields, Tags

LOCAL_LIBRARY_TYPES = {cls.source.lower() for cls in LIBRARY_CLASSES}
REMOTE_LIBRARY_TYPES = {source.casefold() for source in REMOTE_SOURCES}
LIBRARY_TYPES = LOCAL_LIBRARY_TYPES | REMOTE_LIBRARY_TYPES

TAG_ORDER = [field.name.lower() for field in Fields.all()]
# noinspection PyTypeChecker
LOCAL_TRACK_TAG_NAMES: list[str] = list(sorted(
    set(LocalTrackField.__tags__), key=lambda x: TAG_ORDER.index(x)
))


###########################################################################
## Base models
###########################################################################
class PlaylistsConfig(BaseModel):
    filter: Filter = Field(
        description="The filter to apply to available playlists. Filters on playlist names",
        default=FilterComparers(),
    )


class LibraryConfig(BaseModel, metaclass=ABCMeta):
    _type_map: dict[str, Type[BaseModel]]

    name: str = Field(
        description="The user-assigned name of this library",
    )
    type: str = Field(
        description="The source type of this library",
    )
    playlists: PlaylistsConfig = Field(
        description="Configures handling for this library's playlists",
        default=PlaylistsConfig()
    )

    # noinspection PyUnresolvedReferences
    @classmethod
    def create_and_determine_library_type(cls, kwargs: Any | Self) -> Self:
        """
        Create a new :py:class:`.Library` object and determine its type dynamically from the given ``config``
        """
        if not isinstance(kwargs, Mapping):
            return kwargs

        library_type = kwargs.get(type_key := "type", "").strip().casefold()
        if library_type not in cls._type_map.default:
            raise ParserError("Unrecognised library type", key=type_key, value=library_type)

        sub_type = cls._type_map.default[library_type]
        return cls[sub_type](**kwargs)


###########################################################################
###########################################################################
## Local
###########################################################################
class LocalLibraryPathsParser[T: Path | tuple[Path, ...] | None](BaseModel, metaclass=ABCMeta):
    """Base class for parsing and validating library paths config, giving platform appropriate paths."""
    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def _platform_key(cls) -> str:
        platform_map = {"win32": "win", "linux": "lin", "darwin": "mac"}
        return platform_map[sys.platform]

    @computed_field(
        description="The source type of the library associated with these paths",
    )
    @property
    @abstractmethod
    def source(self) -> str:
        """The source type of the library associated with these paths"""
        raise NotImplementedError

    @computed_field(
        description="The paths configured for the current platform",
    )
    @property
    def paths(self) -> T:
        """The path/s configured for the current platform"""
        return self.__getattribute__(self._platform_key)

    @model_validator(mode="after")
    def validate_path_exists(self) -> Self:
        if not self.paths:
            raise ParserError(
                f"No valid paths found for the current platform: {self._platform_key}",
                value=self.paths,
            )

        return self

    @computed_field(
        description="The paths configured for platforms that are not the current platform",
    )
    @property
    def others(self) -> list[Path]:
        """The path/s configured for platforms that are not the current platform"""
        return [
            path
            for key in self.__annotations__ if key != self._platform_key and self.__getattribute__(key) is not None
            for path in to_collection(self.__getattribute__(key))
        ]


class LocalLibraryPaths(LocalLibraryPathsParser[tuple[Path, ...]]):
    """Parses and validates library paths for a :py:class:`LocalLibrary`, giving platform appropriate paths."""
    win: Annotated[tuple[PureWindowsPath, ...], BeforeValidator(to_collection)] | None = Field(
        description="The windows path/s for the MusicBee library",
        default=()
    )
    lin: Annotated[tuple[PurePosixPath, ...], BeforeValidator(to_collection)] | None = Field(
        description="The linux path/s for the MusicBee library",
        default=()
    )
    mac: Annotated[tuple[PurePosixPath, ...], BeforeValidator(to_collection)] | None = Field(
        description="The mac path/s for the MusicBee library",
        default=()
    )

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def source(cls) -> str:
        return str(LocalLibrary.source)

    @model_validator(mode="after")
    def validate_path_is_dir(self) -> Self:
        if not all(Path(path).is_dir() for path in self.paths):
            raise ParserError(
                "The paths given for the current platform are not valid directories",
                value=self.paths,
            )

        return self


class MusicBeePaths(LocalLibraryPathsParser[Path]):
    """Parses and validates library paths for a :py:class:`MusicBee` library, giving platform appropriate paths."""
    win: PureWindowsPath | None = Field(
        description="The windows path for the MusicBee library",
        default=None
    )
    lin: PurePosixPath | None = Field(
        description="The linux path for the MusicBee library",
        default=None
    )
    mac: PurePosixPath | None = Field(
        description="The mac path for the MusicBee library",
        default=None
    )

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def source(cls) -> str:
        return str(MusicBee.source)

    @model_validator(mode="after")
    def validate_path_is_musicbee_lib(self) -> Self:
        if not (path := Path(self.paths).joinpath(MusicBee.xml_library_path)).is_file():
            raise ParserError(
                "No MusicBee library found at the given path",
                value=path,
            )
        if not (path := Path(self.paths).joinpath(MusicBee.xml_settings_path)).is_file():
            raise ParserError(
                "No MusicBee settings found at the given path",
                value=path,
            )

        return self


local_library_defaults = get_default_args(LocalLibrary)


class LocalPaths[T: LocalLibraryPathsParser](BaseModel):
    library: DirectoryPath | list[DirectoryPath] | T = Field(
        description="The path/s for the library folder/s. May be defined as a single path, list of paths, "
                    "or a map with platform specific keys relating to the library path/s for that platform. "
                    f"Recognised platform keys: {tuple(LocalLibraryPaths.__annotations__)}"
    )
    playlists: DirectoryPath | list[DirectoryPath] | None = Field(
        description="The path of the playlist folder",
        default=local_library_defaults.get("playlist_folder")
    )
    map: dict[str, str] = Field(
        description="A map of stems to be used as part of the PathStemMapper",
        default_factory=dict
    )

    @model_validator(mode="after")
    def extend_stem_map_with_other_platforms(self) -> Self:
        if not isinstance(self.library, LocalLibraryPathsParser):
            return self

        if self.map is None:
            self.map = {}

        actual_path = str(next(iter(to_collection(self.library.paths))))
        other_paths = map(str, self.library.others)
        self.map.update({other_path: actual_path for other_path in other_paths if other_path != actual_path})

        return self

updater_defaults = get_default_args(LocalTrack.save)


class UpdaterConfig(BaseModel):
    tags: LocalTrackFields = Field(
        description=f"The tags to be updated. Accepted tags: {LOCAL_TRACK_TAG_NAMES}",
        default=updater_defaults.get("tags", LocalTrackField.ALL)
    )
    replace: bool = Field(default=updater_defaults.get("replace", False))


class TagsConfig(BaseModel):
    rules: Tagger = Field(
        description="The auto-tagger rules",
        default=Tagger(),
    )


class LocalLibraryConfig[T: LocalLibraryPathsParser](LibraryConfig):
    # noinspection PyUnboundLocalVariable
    _type_map: dict[str, Type[LocalLibraryPathsParser]] = PrivateAttr(default={
        "local": LocalLibraryPaths,
        "musicbee": MusicBeePaths,
    })

    # noinspection PyTypeChecker
    paths: LocalPaths[T] = Field(
        description="Configuration for the paths of this local library"
    )
    updater: UpdaterConfig = Field(
        description="Options for tag update operations",
        default=UpdaterConfig()
    )
    tags: TagsConfig = Field(
        description="Options for automatically tagging tracks based on a set of user-defined rules",
        default=TagsConfig()
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def extract_type_from_input(cls, data: Any) -> Any:
        if not isinstance(data, MutableMapping):
            return data

        if (
                isinstance((paths := data.get("paths")), LocalPaths)
                and isinstance((library := paths.library), LocalLibraryPathsParser)
        ):
            data["type"] = library.source

        return data

    @model_validator(mode="after")
    def extract_library_paths(self) -> Self:
        if isinstance(self.paths.library, LocalLibraryPathsParser):
            self.paths.library = self.paths.library.paths
        return self


###########################################################################
## Remote
###########################################################################
api_handler_retry_defaults = get_default_args(GeometricCountTimer)


class APIHandlerRetry(BaseModel):
    initial: NonNegativeFloat = Field(
        description="The initial retry time in seconds for failed requests",
        default=api_handler_retry_defaults.get("initial")
    )
    count: PositiveInt = Field(
        description="The maximum number of request attempts to make before giving up and raising an exception",
        default=api_handler_retry_defaults.get("count")
    )
    factor: confloat(ge=1.0) = Field(
        description="The factor by which to increase retry time for failed requests i.e. value * factor",
        default=api_handler_retry_defaults.get("factor")
    )


api_handler_wait_defaults = get_default_args(StepCeilingTimer)


class APIHandlerWait(BaseModel):
    initial: NonNegativeFloat = Field(
        description="The initial time in seconds to wait after receiving a response from a request",
        default=api_handler_wait_defaults.get("initial")
    )
    final: NonNegativeFloat = Field(
        description="The maximum time in seconds that the wait time can be incremented to",
        default=api_handler_wait_defaults.get("final")
    )
    step: NonNegativeFloat = Field(
        description="The amount in seconds to increase the wait time "
                    "by each time a rate limit is hit i.e. 429 response",
        default=api_handler_wait_defaults.get("step")
    )


class APIHandlerConfig(BaseModel):
    retry: APIHandlerRetry = Field(
        description="Configuration for the timer that controls how long to wait "
                    "in between each successive failed request",
        default=APIHandlerRetry(),
    )
    wait: APIHandlerWait = Field(
        description="Configuration for the timer that controls how long to wait after every request,"
                    " regardless of whether it was successful.",
        default=APIHandlerWait(),
    )


api_cache_defaults = get_default_args(ResponseCache)
local_caches = [SQLiteCache]


class APICacheConfig(BaseModel):
    # noinspection PyTypeHints
    type: Literal[*CACHE_TYPES] | None = Field(
        description=f"The type of backend to connect to. Available types: {", ".join(CACHE_TYPES)}",
        default=None,
    )
    db: str | Path = Field(
        description="The DB to connect to e.g. the URI/path for connecting to an SQLite DB",
        default=None,
    )
    expire_after: timedelta = Field(
        description="The maximum permitted expiry time allowed when looking for a response in the cache. "
                    "Also configures the expiry time to apply for new responses when persisting to the cache. "
                    "Value can be a duration string i.e. [±]P[DD]DT[HH]H[MM]M[SS]S (ISO 8601 format for timedelta)",
        default=api_cache_defaults.get("expire")
    )

    @computed_field(
        description="Is this cache a file system cache that exists on the local system"
    )
    @property
    def is_local(self) -> bool:
        """Is this cache a file system cache that exists on the local system"""
        cls = next((cls for cls in local_caches if cls.type == self.type), None)
        return cls is not None


class APIConfig(BaseModel, metaclass=ABCMeta):
    cache: APICacheConfig = Field(
        description="Configuration for the API cache",
        default=APICacheConfig(),
    )
    handler: APIHandlerConfig = Field(
        description="Configuration for the API handler",
        default=APIHandlerConfig(),
    )
    token_file_path: Path | None = Field(
        description="A path to save/load a response token to",
        default=None,
    )

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    @abstractmethod
    def source(cls) -> str:
        """The source type of the library associated with this API"""
        raise NotImplementedError


class SpotifyAPIConfig(APIConfig):
    client_id: SecretStr = Field(
        description="The client ID to use when authorising requests",
    )
    client_secret: SecretStr = Field(
        description="The client secret to use when authorising requests",
    )
    scope: tuple[str, ...] = Field(
        description="The scopes to request access to",
        default=()
    )

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def source(cls) -> str:
        return str(_SpotifyLibrary.source)


remote_playlists_sync_defaults = get_default_args(RemotePlaylist.sync)
remote_playlists_sync_descriptions = get_arg_descriptions(RemotePlaylist.sync)


class RemotePlaylistsSync(BaseModel):
    kind: PLAYLIST_SYNC_KINDS = Field(
        description=remote_playlists_sync_descriptions.get("kind"),
        default=remote_playlists_sync_defaults.get("kind")
    )
    reload: bool = Field(
        description=remote_playlists_sync_descriptions.get("reload"),
        default=remote_playlists_sync_defaults.get("reload")
    )
    filter: TagFilter = Field(
        description="The filter to apply to tracks before running any sync. "
                    "Parse tag names as the key, any item matching the values given for each corresponding "
                    "tag will be filtered out of any sync operations. "
                    "NOTE: Only `string` value types are currently supported."
                    f"Accepted tags: {LOCAL_TRACK_TAG_NAMES}",
        default_factory=dict
    )


class RemotePlaylistsConfig(PlaylistsConfig):
    sync: RemotePlaylistsSync = Field(
        description="Options for playlist sync operations",
        default=RemotePlaylistsSync(),
    )


remote_item_checker_defaults = get_default_args(RemoteItemChecker)
remote_item_checker_descriptions = get_arg_descriptions(RemoteItemChecker)


class RemoteCheckerConfig(BaseModel):
    interval: int = Field(
        description=remote_item_checker_descriptions.get("interval"),
        default=remote_item_checker_defaults.get("interval")
    )
    allow_karaoke: bool = Field(
        description=remote_item_checker_descriptions.get("allow_karaoke"),
        default=remote_item_checker_defaults.get("allow_karaoke")
    )


item_downloader_default_args = get_default_args(ItemDownloadHelper)


class RemoteItemDownloadConfig(BaseModel):
    urls: UnitSequence[str] = Field(
        description="The template URLs for websites to open queries for."
                    "The given sites should contain exactly 1 '{}' placeholder into which the processor can place"
                    "a query for the item being searched. e.g. *bandcamp.com/search?q={}&item_type=t*",
        default=item_downloader_default_args.get("urls")
    )
    fields: Tags = Field(
        description=f"The tags to use when searching for items. Accepted tags: {LOCAL_TRACK_TAG_NAMES}",
        default=item_downloader_default_args.get("fields")
    )
    interval: conint(ge=1) = Field(
        description="The number of items to open sites for before pausing for user input",
        default=item_downloader_default_args.get("interval"),
    )


class RemoteNewMusicConfig(BaseModel):
    name: str = Field(
        description="The name to give to the new music playlist. When the given playlist name already exists, "
                    "update the tracks in the playlist instead of generating a new one.",
        default="New Music",
    )
    start: date = Field(
        description="The earliest date to get new music for.",
        default=(datetime.now() - timedelta(weeks=4)).date(),
    )
    end: date = Field(
        description="The latest date to get new music for.",
        default=datetime.now().date(),
    )


class RemoteLibraryConfig[T: APIConfig](LibraryConfig):
    _type_map: dict[str, Type[APIConfig]] = PrivateAttr(default={
        "spotify": SpotifyAPIConfig
    })

    api: T = Field(
        description="Configuration for the API of this library",
    )
    # noinspection PyUnresolvedReferences
    playlists: RemotePlaylistsConfig = Field(
        description=LibraryConfig.model_fields.get("playlists").description,
        default=RemotePlaylistsConfig(),
    )
    check: RemoteCheckerConfig = Field(
        description="Configuration for the item checker for this library",
        default=RemoteCheckerConfig(),
    )
    download: RemoteItemDownloadConfig = Field(
        description="Configuration for item downloader operations",
        default=RemoteItemDownloadConfig(),
    )
    new_music: RemoteNewMusicConfig = Field(
        description="Configuration for new music operations",
        default=RemoteNewMusicConfig(),
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def extract_type_from_input(cls, data: Any) -> Any:
        if not isinstance(data, MutableMapping):
            return data

        if isinstance((api := data.get("api")), APIConfig):
            data["type"] = api.source
        return data


###########################################################################
## Combined config
###########################################################################
# noinspection PyTypeChecker
type LocalLibraryAnnotation[T] = Annotated[
    LocalLibraryConfig[T], BeforeValidator(LocalLibraryConfig.create_and_determine_library_type)
]
# noinspection PyTypeChecker
type RemoteLibraryAnnotation[T] = Annotated[
    RemoteLibraryConfig[T], BeforeValidator(RemoteLibraryConfig.create_and_determine_library_type)
]


class LibraryTarget(BaseModel):
    local: str | None = Field(
        description="The name of the local library to use",
        default=None,
    )
    remote: str | None = Field(
        description="The name of the remote library to use",
        default=None,
    )


class LibrariesConfig(BaseModel):
    target: LibraryTarget = Field(
        description="The library targets to use for this run",
        default=LibraryTarget(),
    )
    local: LocalLibraryAnnotation | list[LocalLibraryAnnotation] = Field(
        description="Configuration for all available local libraries",
    )
    remote: RemoteLibraryAnnotation | list[RemoteLibraryAnnotation] = Field(
        description="Configuration for all available remote libraries",
    )

    @model_validator(mode="after")
    def extract_local_library_from_target(self) -> Self:
        if not isinstance(self.local, list):
            return self

        if not self.target.local:
            raise ParserError("Many local libraries given but no target specified", key="local")

        self.local: list[LocalLibraryConfig]
        try:
            self.local = next(iter(lib for lib in self.local if lib.name == self.target.local))
        except StopIteration:
            raise ParserError(
                "The given local target does not correspond to any configured local library", key="local"
                )

        return self

    @model_validator(mode="after")
    def extract_remote_library_from_target(self) -> Self:
        if not isinstance(self.remote, list):
            return self

        if not self.target.remote:
            raise ParserError("Many remote libraries given but no target specified", key="local")

        self.remote: list[RemoteLibraryConfig]
        try:
            self.remote = next(iter(lib for lib in self.remote if lib.name == self.target.remote))
        except StopIteration:
            raise ParserError(
                "The given remote target does not correspond to any configured remote library", key="remote"
            )

        return self
