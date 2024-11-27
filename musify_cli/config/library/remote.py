from abc import ABCMeta, abstractmethod
from collections.abc import Collection
from copy import copy
from datetime import timedelta, date, datetime
from pathlib import Path
from typing import Literal, ClassVar

from aiorequestful.cache.backend import ResponseCache, SQLiteCache, CACHE_TYPES, CACHE_CLASSES
from aiorequestful.timer import Timer, GeometricCountTimer, StepCeilingTimer
from aiorequestful.types import UnitSequence
from musify.libraries.core.object import Playlist
from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.core.library import RemoteLibrary, SyncPlaylistsType
from musify.libraries.remote.core.object import PLAYLIST_SYNC_KINDS, RemotePlaylist, RemoteAlbum, \
    SyncResultRemotePlaylist
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.factory import SpotifyObjectFactory
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from musify.processors.check import RemoteItemChecker
from musify.processors.download import ItemDownloadHelper
from musify.processors.match import ItemMatcher
from musify.processors.search import RemoteItemSearcher
from musify.utils import get_max_width, align_string, to_collection
from pydantic import BaseModel, NonNegativeFloat, Field, PositiveInt, confloat, computed_field, SecretStr, conint

from musify_cli.config.library._core import LibraryConfig, PlaylistsConfig, Instantiator, Runner
from musify_cli.config.operations.signature import get_default_args, get_arg_descriptions
from musify_cli.config.operations.tags import TAG_NAMES, TagFilter, Tags
from musify_cli.exception import ParserError

###########################################################################
## Operations
###########################################################################
remote_item_checker_defaults = get_default_args(RemoteItemChecker)
remote_item_checker_descriptions = get_arg_descriptions(RemoteItemChecker)


class RemoteCheckerConfig(Instantiator[RemoteItemChecker]):
    interval: int = Field(
        description=remote_item_checker_descriptions.get("interval"),
        default=remote_item_checker_defaults.get("interval")
    )
    allow_karaoke: bool = Field(
        description=remote_item_checker_descriptions.get("allow_karaoke"),
        default=remote_item_checker_defaults.get("allow_karaoke")
    )

    def create(self, factory: RemoteObjectFactory, matcher: ItemMatcher = None):
        return RemoteItemChecker(
            matcher=matcher or ItemMatcher(),
            object_factory=factory,
            interval=self.interval,
            allow_karaoke=self.allow_karaoke
        )


class RemoteItemSearcherConfig(Instantiator[RemoteItemSearcher]):
    def create(self, factory: RemoteObjectFactory, matcher: ItemMatcher = None):
        return RemoteItemSearcher(matcher=matcher or ItemMatcher(), object_factory=factory)


item_downloader_default_args = get_default_args(ItemDownloadHelper)


class RemoteItemDownloadConfig(Instantiator[ItemDownloadHelper]):
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

    def create(self):
        return ItemDownloadHelper(urls=self.urls, fields=self.fields, interval=self.interval)


class RemoteNewMusicConfig(Runner[tuple[str, SyncResultRemotePlaylist]]):
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

    async def run(self, library: RemoteLibrary, dry_run: bool = True):
        """
        Create a new music playlist for followed artists with music released between ``start`` and ``end``.

        :param library: The library within which to create/update the playlist.
        :param dry_run: Run function, but do not modify the library's playlists at all.
        :return: The name of the new playlist and results of the sync as a :py:class:`SyncResultRemotePlaylist` object.
        """
        collections = self._filter_artist_albums_by_date(library)

        collections = to_collection(collections)
        tracks = [
            track for collection in sorted(collections, key=lambda x: x.date, reverse=True) for track in collection
        ]

        self._logger.info(
            f"\33[1;95m  >\33[1;97m Creating {self.name!r} {library.source} playlist "
            f"for {len(tracks)} new tracks by followed artists released between {self.start} and {self.end}\33[0m"
        )

        # add tracks to remote playlist
        response = await library.api.get_or_create_playlist(self.name)
        pl: RemotePlaylist = library.factory.playlist(response, skip_checks=True)
        pl.clear()
        pl.extend(tracks, allow_duplicates=False)
        return self.name, await pl.sync(kind="refresh", reload=False, dry_run=dry_run)

    def _filter_artist_albums_by_date(self, library: RemoteLibrary) -> list[RemoteAlbum]:
        """Returns all loaded artist albums that are within the given ``start`` and ``end`` dates inclusive"""
        def match_date(alb: RemoteAlbum) -> bool:
            """Match start and end dates to the release date of the given ``alb``"""
            if alb.date:
                return self.start <= alb.date <= self.end
            if alb.month:
                return self.start.year <= alb.year <= self.end.year and self.start.month <= alb.month <= self.end.month
            if alb.year:
                return self.start.year <= alb.year <= self.end.year
            return False

        return list(filter(match_date, (album for artist in library.artists for album in artist.albums)))


###########################################################################
## API
###########################################################################
api_handler_retry_defaults = get_default_args(GeometricCountTimer)


class APIHandlerRetry(Instantiator[Timer]):
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

    def create(self):
        return GeometricCountTimer(initial=self.initial, count=self.count, factor=self.factor)


api_handler_wait_defaults = get_default_args(StepCeilingTimer)


class APIHandlerWait(Instantiator[Timer]):
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

    def create(self):
        return StepCeilingTimer(initial=self.initial, final=self.final, step=self.step)


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


class APICacheConfig(Instantiator[ResponseCache]):
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

    def create(self, name: str):
        cls = next((cls for cls in CACHE_CLASSES if cls.type == self.type), None)
        return cls.connect(value=self.db, expire=self.expire_after)


class APIConfig[T: RemoteAPI](Instantiator[T], metaclass=ABCMeta):
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


class SpotifyAPIConfig(APIConfig[SpotifyAPI]):
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

    def create(self):
        if not self.client_id or not self.client_secret:
            raise ParserError("Cannot create API object without client ID and client secret")

        return SpotifyAPI(
            client_id=self.client_id.get_secret_value(),
            client_secret=self.client_secret.get_secret_value(),
            scope=self.scope,
            cache=self.cache.create(str(SpotifyAPI.source)),
            token_file_path=self.token_file_path,
        )


###########################################################################
## Main
###########################################################################
remote_playlists_sync_defaults = get_default_args(RemotePlaylist.sync)
remote_playlists_sync_descriptions = get_arg_descriptions(RemotePlaylist.sync)


class RemotePlaylistsSync(Runner[dict[str, SyncResultRemotePlaylist]]):
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

    async def run(self, library: RemoteLibrary, playlists: Collection[Playlist] = None, dry_run: bool = True):
        """
        Sync the given ``playlists`` with the instantiated remote library.

        :param library: The library containing playlists to be synchronised
        :param playlists: The playlists to be synchronised with the library's playlists.
        :param dry_run: Run function, but do not modify the library's playlists at all.
        :return: Map of playlist name to the results of the sync as a :py:class:`SyncResultRemotePlaylist` object.
        """
        playlists = list(map(copy, playlists))
        for pl in playlists:  # so filter_playlists doesn't clear the list of tracks on the original playlist objects
            pl._tracks = pl.tracks.copy()

        return await library.sync(
            playlists=self._filter_playlists(playlists=playlists),
            kind=self.kind,
            reload=self.reload,
            dry_run=dry_run,
        )

    def _filter_playlists[T: Playlist](self, playlists: Collection[T]) -> Collection[T]:
        """
        Returns a filtered set of the given ``playlists`` according to the config for this library.

        :param playlists: The playlists to be filtered.
        :return: Filtered playlists.
        """
        tag_filter = self.filter
        self._logger.info(
            f"\33[1;95m ->\33[1;97m Filtering playlists and tracks from {len(playlists)} playlists\n"
            f"\33[0;90m    Filter out tags: {tag_filter} \33[0m"
        )

        max_width = get_max_width([pl.name for pl in playlists])
        for pl in playlists:
            initial_count = len(pl)
            tracks = []
            for track in pl.tracks:
                keep = True

                for tag, values in tag_filter.items():
                    item_val = str(track[tag])

                    if any(v.strip().casefold() in item_val.strip().casefold() for v in values):
                        keep = False
                        break

                if keep:
                    tracks.append(track)

            pl.clear()
            pl.extend(tracks)

            self._logger.debug(
                f"{align_string(pl.name, max_width=max_width)} | Filtered out {initial_count - len(pl):>3} items"
            )

        self._logger.print_line()
        return playlists


class RemotePlaylistsConfig(PlaylistsConfig):
    sync: RemotePlaylistsSync = Field(
        description="Options for playlist sync operations",
        default=RemotePlaylistsSync(),
    )


class RemoteLibraryConfig[L: RemoteLibrary, A: APIConfig](LibraryConfig[RemoteLibrary], metaclass=ABCMeta):

    _library_cls: ClassVar[type[RemoteLibrary]] = RemoteLibrary

    api: A = Field(
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
    search: RemoteItemSearcherConfig = Field(
        description="Configuration for the item searcher for this library",
        default=RemoteItemSearcherConfig(),
    )
    download: RemoteItemDownloadConfig = Field(
        description="Configuration for item downloader operations",
        default=RemoteItemDownloadConfig(),
    )
    new_music: RemoteNewMusicConfig = Field(
        description="Configuration for new music operations",
        default=RemoteNewMusicConfig(),
    )

    @property
    @abstractmethod
    def factory(self) -> RemoteObjectFactory:
        """The remote object factory for this remote library type"""
        raise NotImplementedError

    @property
    @abstractmethod
    def wrangler(self) -> RemoteDataWrangler:
        """The initialised remote data wrangler for this remote library type"""
        raise NotImplementedError

    def create(self):
        return self._library_cls(api=self.api.create(), playlist_filter=self.playlists.filter)


class SpotifyLibraryConfig(RemoteLibraryConfig[SpotifyLibrary, SpotifyAPIConfig]):

    _library_cls: ClassVar[type[SpotifyLibrary]] = SpotifyLibrary

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def source(cls) -> str:
        """The source type of the library"""
        return str(cls._library_cls.source)

    @property
    def factory(self) -> SpotifyObjectFactory:
        return SpotifyObjectFactory()

    @property
    def wrangler(self) -> SpotifyDataWrangler:
        return SpotifyDataWrangler()


REMOTE_LIBRARY_CONFIG: frozenset[type[RemoteLibraryConfig]] = frozenset({
    SpotifyLibraryConfig,
})
