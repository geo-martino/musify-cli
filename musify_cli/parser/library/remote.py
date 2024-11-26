from abc import ABCMeta, abstractmethod
from datetime import timedelta, date, datetime
from pathlib import Path
from typing import Literal, Type, Any, MutableMapping

from aiorequestful.cache.backend import ResponseCache, SQLiteCache, CACHE_TYPES
from aiorequestful.timer import GeometricCountTimer, StepCeilingTimer
from aiorequestful.types import UnitSequence
from musify.libraries.remote import REMOTE_SOURCES
from musify.libraries.remote.core.object import RemotePlaylist, PLAYLIST_SYNC_KINDS
from musify.libraries.remote.spotify.library import SpotifyLibrary as _SpotifyLibrary
from musify.processors.check import RemoteItemChecker
from musify.processors.download import ItemDownloadHelper
from pydantic import BaseModel, NonNegativeFloat, Field, PositiveInt, confloat, computed_field, SecretStr, conint, \
    PrivateAttr, model_validator

from musify_cli.parser.library._core import LibraryConfig, PlaylistsConfig
from musify_cli.parser.operations.signature import get_default_args, get_arg_descriptions
from musify_cli.parser.operations.tags import TAG_NAMES, TagFilter, Tags

REMOTE_LIBRARY_TYPES = {source.casefold() for source in REMOTE_SOURCES}

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
                    f"Accepted tags: {TAG_NAMES}",
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
        description=f"The tags to use when searching for items. Accepted tags: {TAG_NAMES}",
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
        """Attempt to infer and set the ``type`` field from the other input fields"""
        if not isinstance(data, MutableMapping):
            return data

        if isinstance((api := data.get("api")), APIConfig):
            data["type"] = api.source
        return data
