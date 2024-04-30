from abc import ABCMeta, abstractmethod
from collections.abc import Collection
from datetime import datetime

from jsonargparse import Namespace
from musify.libraries.core.object import Playlist
from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.enum import RemoteObjectType
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.core.library import RemoteLibrary
from musify.libraries.remote.core.object import SyncResultRemotePlaylist, RemotePlaylist, RemoteAlbum
from musify.libraries.remote.core.processors.check import RemoteItemChecker
from musify.libraries.remote.core.processors.search import RemoteItemSearcher
from musify.libraries.remote.core.processors.wrangle import RemoteDataWrangler
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.factory import SpotifyObjectFactory
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.libraries.remote.spotify.processors import SpotifyDataWrangler
from musify.log import STAT
from musify.processors.match import ItemMatcher
from musify.types import UnitCollection
from musify.utils import get_max_width, align_string, to_collection

from musify_cli.exception import ParserError
from musify_cli.manager.library._core import LibraryManager
from musify_cli.parser import LoadTypesRemote, EnrichTypesRemote


class RemoteLibraryManager(LibraryManager, metaclass=ABCMeta):
    """Instantiates and manages a :py:class:`RemoteLibrary` and related objects from a given ``config``."""

    def __init__(self, name: str, config: Namespace, dry_run: bool = True):
        super().__init__(name=name, config=config, dry_run=dry_run)

        self._library: RemoteLibrary | None = None
        self._api: RemoteAPI | None = None

        # utilities
        self._factory: RemoteObjectFactory | None = None
        self._wrangler: RemoteDataWrangler | None = None

        self.types_loaded: set[LoadTypesRemote] = set()
        self.extended: bool = False
        self.types_enriched: dict[LoadTypesRemote, set[EnrichTypesRemote]] = {}

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

    @property
    def use_cache(self) -> bool:
        """Whether to use the cache when calling the API endpoint"""
        return self.config.api.use_cache

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
            use_cache=self.use_cache,
        )

    ###########################################################################
    ## Operations
    ###########################################################################
    def load(self, types: UnitCollection[LoadTypesRemote] = (), force: bool = False) -> None:
        def _loaded(load_type: LoadTypesRemote) -> bool:
            return load_type in self.types_loaded

        def _should_load(load_type: LoadTypesRemote) -> bool:
            selected = not types or load_type in types
            can_be_loaded = force or not _loaded(load_type)
            return selected and can_be_loaded

        types = to_collection(types)

        if not types and (force or not self.types_loaded):
            self.library.load()
            self.types_loaded.update(LoadTypesRemote.all())
            return

        if _should_load(LoadTypesRemote.playlists):
            self.library.load_playlists()
            self.types_loaded.add(LoadTypesRemote.playlists)
        if _should_load(LoadTypesRemote.saved_tracks):
            self.library.load_tracks()
            self.types_loaded.add(LoadTypesRemote.saved_tracks)
        if _should_load(LoadTypesRemote.saved_albums):
            self.library.load_saved_albums()
            self.types_loaded.add(LoadTypesRemote.saved_albums)
        if _should_load(LoadTypesRemote.saved_artists):
            self.library.load_saved_artists()
            self.types_loaded.add(LoadTypesRemote.saved_artists)

        self.logger.print(STAT)
        if _loaded(LoadTypesRemote.playlists):
            self.library.log_playlists()
        if _loaded(LoadTypesRemote.saved_tracks):
            self.library.log_tracks()
        if _loaded(LoadTypesRemote.saved_albums):
            self.library.log_albums()
        if _loaded(LoadTypesRemote.saved_artists):
            self.library.log_albums()
        self.logger.print()

    def enrich(
            self,
            types: UnitCollection[LoadTypesRemote] = (),
            enrich: UnitCollection[EnrichTypesRemote] = (),
            force: bool = False
    ):
        """
        Enrich items/collections in the instantiated library based on the given ``types``.

        :param types: The types of items/collections to enrich.
        :param force: Whether to enrich the given ``types`` even if they have already been enriched before.
            When False, only enrich the ``types`` that have not been enriched.
        """
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

        types = to_collection(types)
        enrich = to_collection(enrich)

        if _loaded(LoadTypesRemote.saved_tracks) and (force or not _enriched(LoadTypesRemote.saved_tracks)):
            artists = _should_enrich(LoadTypesRemote.saved_tracks, EnrichTypesRemote.artists)
            albums = _should_enrich(LoadTypesRemote.saved_tracks, EnrichTypesRemote.albums)
            self.library.enrich_tracks(artists=artists, albums=albums)

            types_enriched = self.types_enriched.get(LoadTypesRemote.saved_tracks, set())
            if artists:
                types_enriched.add(EnrichTypesRemote.artists)
            if albums:
                types_enriched.add(EnrichTypesRemote.albums)
            self.types_enriched[LoadTypesRemote.saved_tracks] = types_enriched
        if _loaded(LoadTypesRemote.saved_albums) and (force or not _enriched(LoadTypesRemote.saved_albums)):
            self.library.enrich_saved_albums()
            self.types_enriched[LoadTypesRemote.saved_albums] = set()
        if _loaded(LoadTypesRemote.saved_artists) and (force or not _enriched(LoadTypesRemote.saved_artists)):
            tracks = _should_enrich(LoadTypesRemote.saved_artists, EnrichTypesRemote.tracks)
            self.library.enrich_saved_artists(tracks=tracks)

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

        self.logger.print()
        return pl_filtered

    def sync(self, playlists: Collection[Playlist]) -> dict[str, SyncResultRemotePlaylist]:
        """
        Sync the given ``playlists`` with the instantiated remote library.

        :param playlists: The playlists to be synchronised.
        :return: Map of playlist name to the results of the sync as a :py:class:`SyncResultRemotePlaylist` object.
        """
        playlists = self._filter_playlists(playlists=playlists)
        return self.library.sync(
            playlists=playlists,
            kind=self.config.playlists.sync.kind,
            reload=self.config.playlists.sync.reload,
            dry_run=self.dry_run
        )

    def get_or_create_playlist(self, name: str) -> RemotePlaylist:
        """
        Get the loaded playlist with the given ``name`` and return it.
        If not found, attempt to find the playlist and load it (ignoring ``use_cache`` settings)
        Otherwise, create a new playlist.
        """
        pl = self.library.playlists.get(name)
        if pl is None:  # playlist not loaded, attempt to find playlist on remote with fresh data
            responses = self.api.get_user_items(use_cache=False)
            for response in responses:
                pl_check = self.factory.playlist(response=response, skip_checks=True)

                if pl_check.name == name:
                    self.api.get_items(pl_check, kind=RemoteObjectType.PLAYLIST, use_cache=False)
                    pl = pl_check
                    break

        if pl is None:  # if playlist still not found, create it
            # noinspection PyArgumentList
            pl = self.factory.playlist.create(name=name)

        return pl

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
            self._library = SpotifyLibrary(
                api=self.api,
                use_cache=self.use_cache,
                playlist_filter=self.playlist_filter or (),
            )
        return self._library

    @property
    def api(self) -> SpotifyAPI:
        if self._api is None:
            if not self.config.api.client_id or not self.config.api.client_secret:
                raise ParserError("Cannot create API object without client ID and client secret")

            self._api = SpotifyAPI(
                client_id=self.config.api.client_id,
                client_secret=self.config.api.client_secret,
                scopes=self.config.api.scopes,
                token_file_path=self.config.api.token_path,
                cache_path=self.config.api.cache_path,
            )
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
