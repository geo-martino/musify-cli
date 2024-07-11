from abc import ABCMeta, abstractmethod
from collections.abc import Collection
from datetime import datetime
from typing import AsyncContextManager, Self

from aiorequestful.cache.backend import CACHE_CLASSES, ResponseCache
from aiorequestful.request.timer import PowerCountTimer, StepCeilingTimer
from jsonargparse import Namespace
from musify.libraries.core.object import Playlist
from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.core.library import RemoteLibrary
from musify.libraries.remote.core.object import SyncResultRemotePlaylist, RemoteAlbum
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.factory import SpotifyObjectFactory
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from musify.logger import STAT
from musify.processors.check import RemoteItemChecker
from musify.processors.match import ItemMatcher
from musify.processors.search import RemoteItemSearcher
from musify.types import UnitCollection
from musify.utils import get_max_width, align_string, to_collection

from musify_cli.exception import ParserError
from musify_cli.manager.library._core import LibraryManager
from musify_cli.parser import LoadTypesRemote, EnrichTypesRemote


class RemoteLibraryManager(LibraryManager, AsyncContextManager, metaclass=ABCMeta):
    """Instantiates and manages a :py:class:`RemoteLibrary` and related objects from a given ``config``."""

    def __init__(self, name: str, config: Namespace, dry_run: bool = True):
        super().__init__(name=name, config=config, dry_run=dry_run)

        self._library: RemoteLibrary | None = None
        self._api: RemoteAPI | None = None

        # utilities
        self._cache: ResponseCache | None = None
        self._factory: RemoteObjectFactory | None = None
        self._wrangler: RemoteDataWrangler | None = None

        self.types_loaded: set[LoadTypesRemote] = set()
        self.extended: bool = False
        self.types_enriched: dict[LoadTypesRemote, set[EnrichTypesRemote]] = {}

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.check.close()
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def source(self) -> str:
        return self.wrangler.source

    @property
    @abstractmethod
    def library(self) -> RemoteLibrary:
        """The initialised remote library"""
        raise NotImplementedError

    @property
    @abstractmethod
    def api(self) -> RemoteAPI:
        """The initialised remote API for this remote library type"""
        raise NotImplementedError

    def _set_handler(self, api: RemoteAPI) -> None:
        config: Namespace = self.config.api.handler
        if not self.config.api.handler:
            return

        if config_retry := config.get("retry") and config.retry.enabled:
            api.handler.retry_timer = PowerCountTimer(**config_retry)
        if config_wait := config.get("wait") and config.wait.enabled:
            api.handler.wait_timer = StepCeilingTimer(**config_wait)

    @property
    def cache(self) -> ResponseCache | None:
        """The initialised cache to use with the remote API for this remote library type"""
        if self._cache is None:
            config = self.config.api.cache
            if config is None:
                return

            cls = next((cls for cls in CACHE_CLASSES if cls.type == config.type), None)
            if not cls:
                return

            self._cache = cls.connect(value=config.db, expire=config.expire_after)

        return self._cache

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

    @property
    def match(self) -> ItemMatcher:
        """The initialised item matcher for this remote library type"""
        return ItemMatcher()

    @property
    def check(self) -> RemoteItemChecker:
        """The initialised remote item checker for this remote library type"""
        return RemoteItemChecker(
            matcher=self.match,
            object_factory=self.factory,
            interval=self.config.check.interval,
            allow_karaoke=self.config.check.allow_karaoke,
        )

    @property
    def search(self) -> RemoteItemSearcher:
        """The initialised remote item searcher for this remote library type"""
        return RemoteItemSearcher(
            matcher=self.match,
            object_factory=self.factory,
        )

    ###########################################################################
    ## Operations
    ###########################################################################
    async def load(self, types: UnitCollection[LoadTypesRemote] = (), force: bool = False) -> None:
        def _should_load(load_type: LoadTypesRemote) -> bool:
            selected = not types or load_type in types
            can_be_loaded = force or load_type not in self.types_loaded
            return selected and can_be_loaded

        types = to_collection(types)

        if types and self.types_loaded.intersection(types) == set(types) and not force:
            return
        elif not types and (force or not self.types_loaded):
            await self.library.load()
            self.types_loaded.update(LoadTypesRemote.all())
            return

        loaded = set()
        if _should_load(LoadTypesRemote.playlists):
            await self.library.load_playlists()
            self.types_loaded.add(LoadTypesRemote.playlists)
            loaded.add(LoadTypesRemote.playlists)
        if _should_load(LoadTypesRemote.saved_tracks):
            await self.library.load_tracks()
            self.types_loaded.add(LoadTypesRemote.saved_tracks)
            loaded.add(LoadTypesRemote.saved_tracks)
        if _should_load(LoadTypesRemote.saved_albums):
            await self.library.load_saved_albums()
            self.types_loaded.add(LoadTypesRemote.saved_albums)
            loaded.add(LoadTypesRemote.saved_albums)
        if _should_load(LoadTypesRemote.saved_artists):
            await self.library.load_saved_artists()
            self.types_loaded.add(LoadTypesRemote.saved_artists)
            loaded.add(LoadTypesRemote.saved_artists)

        if not loaded:
            return

        self.logger.print_line(STAT)
        if LoadTypesRemote.playlists in loaded:
            self.library.log_playlists()
        if LoadTypesRemote.saved_tracks in loaded:
            self.library.log_tracks()
        if LoadTypesRemote.saved_albums in loaded:
            self.library.log_albums()
        if LoadTypesRemote.saved_artists in loaded:
            self.library.log_artists()
        self.logger.print_line()

    async def enrich(
            self,
            types: UnitCollection[LoadTypesRemote] = (),
            enrich: UnitCollection[EnrichTypesRemote] = (),
            force: bool = False
    ):
        """
        Enrich items/collections in the instantiated library based on the given ``types``.

        :param types: The types of loaded items/collections to enrich.
        :param enrich: The types of items/collections which should be enriched for each of the loaded ``types``.
        :param force: Whether to enrich the given ``types`` even if they have already been enriched before.
            When False, only enrich the ``types`` that have not been enriched.
        """
        types = to_collection(types)
        enrich = to_collection(enrich)

        def _loaded(load_type: LoadTypesRemote) -> bool:
            selected = not types or load_type in types
            return selected and load_type in self.types_loaded

        def _enriched(load_type: LoadTypesRemote) -> bool:
            enriched = self.types_enriched.get(load_type, [])
            return load_type in self.types_enriched or all(t in enriched for t in types or EnrichTypesRemote.all())

        def _should_enrich(load_type: LoadTypesRemote, enrich_type: EnrichTypesRemote) -> bool:
            selected = not enrich or enrich_type in enrich
            can_be_loaded = force or enrich_type not in self.types_enriched.get(load_type, [])
            return selected and can_be_loaded

        if _loaded(LoadTypesRemote.saved_tracks) and (force or not _enriched(LoadTypesRemote.saved_tracks)):
            artists = _should_enrich(LoadTypesRemote.saved_tracks, EnrichTypesRemote.artists)
            albums = _should_enrich(LoadTypesRemote.saved_tracks, EnrichTypesRemote.albums)
            await self.library.enrich_tracks(artists=artists, albums=albums)

            types_enriched = self.types_enriched.get(LoadTypesRemote.saved_tracks, set())
            if artists:
                types_enriched.add(EnrichTypesRemote.artists)
            if albums:
                types_enriched.add(EnrichTypesRemote.albums)
            self.types_enriched[LoadTypesRemote.saved_tracks] = types_enriched
        if _loaded(LoadTypesRemote.saved_albums) and (force or not _enriched(LoadTypesRemote.saved_albums)):
            await self.library.enrich_saved_albums()
            self.types_enriched[LoadTypesRemote.saved_albums] = set()
        if _loaded(LoadTypesRemote.saved_artists) and (force or not _enriched(LoadTypesRemote.saved_artists)):
            tracks = _should_enrich(LoadTypesRemote.saved_artists, EnrichTypesRemote.tracks)
            await self.library.enrich_saved_artists(tracks=tracks)

            types_enriched = self.types_enriched.get(LoadTypesRemote.saved_artists, set())
            if tracks:
                types_enriched.add(EnrichTypesRemote.tracks)
            self.types_enriched[LoadTypesRemote.saved_artists] = types_enriched

    def _filter_playlists[T: Playlist](self, playlists: Collection[T]) -> Collection[T]:
        """
        Returns a filtered set of the given ``playlists`` according to the config for this library.

        :param playlists: The playlists to be filtered.
        :return: Filtered playlists.
        """
        tag_filter = self.config.playlists.sync.filter
        self.logger.info(
            f"\33[1;95m ->\33[1;97m Filtering playlists and tracks from {len(playlists)} playlists\n"
            f"\33[0;90m    Filter out tags: {tag_filter} \33[0m"
        )

        pl_filtered: Collection[T] = self.playlist_filter(playlists) if self.playlist_filter is not None else playlists

        max_width = get_max_width([pl.name for pl in pl_filtered])
        for pl in pl_filtered:
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

            self.logger.debug(
                f"{align_string(pl.name, max_width=max_width)} | Filtered out {initial_count - len(pl):>3} items"
            )

        self.logger.print_line()
        return pl_filtered

    async def sync(self, playlists: Collection[Playlist]) -> dict[str, SyncResultRemotePlaylist]:
        """
        Sync the given ``playlists`` with the instantiated remote library.

        :param playlists: The playlists to be synchronised.
        :return: Map of playlist name to the results of the sync as a :py:class:`SyncResultRemotePlaylist` object.
        """
        playlists = self._filter_playlists(playlists=playlists)
        return await self.library.sync(
            playlists=playlists,
            kind=self.config.playlists.sync.kind,
            reload=self.config.playlists.sync.reload,
            dry_run=self.dry_run
        )

    def filter_artist_albums_by_date(self, start: datetime.date, end: datetime.date) -> list[RemoteAlbum]:
        """Returns all loaded artist albums that are within the given ``start`` and ``end`` dates inclusive"""
        def match_date(alb: RemoteAlbum) -> bool:
            """Match start and end dates to the release date of the given ``alb``"""
            if alb.date:
                return start <= alb.date <= end
            if alb.month:
                return start.year <= alb.year <= end.year and start.month <= alb.month <= end.month
            if alb.year:
                return start.year <= alb.year <= end.year
            return False

        return [album for artist in self.library.artists for album in artist.albums if match_date(album)]


class SpotifyLibraryManager(RemoteLibraryManager):
    """Instantiates and manages a generic :py:class:`SpotifyLibrary` and related objects from a given ``config``."""

    @property
    def library(self) -> SpotifyLibrary:
        if self._library is None:
            self._library = SpotifyLibrary(api=self.api, playlist_filter=self.playlist_filter or ())
            self.initialised = True

        return self._library

    @property
    def api(self) -> SpotifyAPI:
        if self._api is None:
            if not self.config.api.client_id or not self.config.api.client_secret:
                raise ParserError("Cannot create API object without client ID and client secret")

            self._api = SpotifyAPI(
                client_id=self.config.api.client_id,
                client_secret=self.config.api.client_secret,
                scope=self.config.api.scope,
                cache=self.cache,
                token_file_path=self.config.api.token_file_path,
            )
            self.initialised = True

            self._set_handler(self._api)

        return self._api

    @property
    def factory(self) -> SpotifyObjectFactory:
        if self._factory is None:
            self._factory = SpotifyObjectFactory(api=self.api)
        return self._factory

    @property
    def wrangler(self) -> SpotifyDataWrangler:
        if self._wrangler is None:
            self._wrangler = SpotifyDataWrangler()
        return self._wrangler
