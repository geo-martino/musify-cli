from functools import cached_property
from typing import AsyncContextManager, Self

from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.core.library import RemoteLibrary
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.logger import STAT
from musify.processors.check import RemoteItemChecker
from musify.processors.download import ItemDownloadHelper
from musify.processors.match import ItemMatcher
from musify.processors.search import RemoteItemSearcher
from musify.types import UnitCollection
from musify.utils import to_collection

from musify_cli.config.library.remote import RemoteLibraryConfig
from musify_cli.config.library.types import LoadTypesRemote, EnrichTypesRemote
from musify_cli.manager.library._core import LibraryManager


class RemoteLibraryManager[L: RemoteLibrary, C: RemoteLibraryConfig](LibraryManager[L, C], AsyncContextManager):
    """Instantiates and manages a :py:class:`RemoteLibrary` and related objects from a given ``config``."""

    def __init__(self, config: RemoteLibraryConfig, dry_run: bool = True):
        super().__init__(config=config, dry_run=dry_run)

        self.types_loaded: set[LoadTypesRemote] = set()
        self.extended: bool = False
        self.types_enriched: dict[LoadTypesRemote, set[EnrichTypesRemote]] = {}

    async def __aenter__(self) -> Self:
        if self.initialised:
            await self.api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.check.close()
        if self.initialised:
            await self.api.__aexit__(exc_type, exc_val, exc_tb)

    @cached_property
    def api(self) -> RemoteAPI:
        """The initialised remote API for this remote library type"""
        self.initialised = True
        return self.config.api.create()

    @cached_property
    def factory(self) -> RemoteObjectFactory:
        """The remote object factory for this remote library type"""
        factory = self.config.factory
        factory.api = self.api
        return factory

    @cached_property
    def wrangler(self) -> RemoteDataWrangler:
        """The initialised remote data wrangler for this remote library type"""
        return self.config.wrangler

    @cached_property
    def match(self) -> ItemMatcher:
        """The initialised item matcher for this remote library type"""
        return ItemMatcher()

    @property
    def check(self) -> RemoteItemChecker:
        """The initialised remote item checker for this remote library type"""
        return self.config.check.create(factory=self.factory, matcher=self.match)

    @property
    def search(self) -> RemoteItemSearcher:
        """The initialised remote item searcher for this remote library type"""
        return self.config.search.create(factory=self.factory, matcher=self.match)

    @property
    def download(self) -> ItemDownloadHelper:
        """The initialised remote download helper for this remote library type"""
        return self.config.download.create()

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
        if _should_load(LoadTypesRemote.PLAYLISTS):
            await self.library.load_playlists()
            self.types_loaded.add(LoadTypesRemote.PLAYLISTS)
            loaded.add(LoadTypesRemote.PLAYLISTS)
        if _should_load(LoadTypesRemote.SAVED_TRACKS):
            await self.library.load_tracks()
            self.types_loaded.add(LoadTypesRemote.SAVED_TRACKS)
            loaded.add(LoadTypesRemote.SAVED_TRACKS)
        if _should_load(LoadTypesRemote.SAVED_ALBUMS):
            await self.library.load_saved_albums()
            self.types_loaded.add(LoadTypesRemote.SAVED_ALBUMS)
            loaded.add(LoadTypesRemote.SAVED_ALBUMS)
        if _should_load(LoadTypesRemote.SAVED_ARTISTS):
            await self.library.load_saved_artists()
            self.types_loaded.add(LoadTypesRemote.SAVED_ARTISTS)
            loaded.add(LoadTypesRemote.SAVED_ARTISTS)

        if not loaded:
            return

        self.logger.print_line(STAT)
        if LoadTypesRemote.PLAYLISTS in loaded:
            self.library.log_playlists()
        if LoadTypesRemote.SAVED_TRACKS in loaded:
            self.library.log_tracks()
        if LoadTypesRemote.SAVED_ALBUMS in loaded:
            self.library.log_albums()
        if LoadTypesRemote.SAVED_ARTISTS in loaded:
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

        if _loaded(LoadTypesRemote.SAVED_TRACKS) and (force or not _enriched(LoadTypesRemote.SAVED_TRACKS)):
            artists = _should_enrich(LoadTypesRemote.SAVED_TRACKS, EnrichTypesRemote.ARTISTS)
            albums = _should_enrich(LoadTypesRemote.SAVED_TRACKS, EnrichTypesRemote.ALBUMS)
            await self.library.enrich_tracks(artists=artists, albums=albums)

            types_enriched = self.types_enriched.get(LoadTypesRemote.SAVED_TRACKS, set())
            if artists:
                types_enriched.add(EnrichTypesRemote.ARTISTS)
            if albums:
                types_enriched.add(EnrichTypesRemote.ALBUMS)
            self.types_enriched[LoadTypesRemote.SAVED_TRACKS] = types_enriched
        if _loaded(LoadTypesRemote.SAVED_ALBUMS) and (force or not _enriched(LoadTypesRemote.SAVED_ALBUMS)):
            await self.library.enrich_saved_albums()
            self.types_enriched[LoadTypesRemote.SAVED_ALBUMS] = set()
        if _loaded(LoadTypesRemote.SAVED_ARTISTS) and (force or not _enriched(LoadTypesRemote.SAVED_ARTISTS)):
            tracks = _should_enrich(LoadTypesRemote.SAVED_ARTISTS, EnrichTypesRemote.TRACKS)
            await self.library.enrich_saved_artists(tracks=tracks)

            types_enriched = self.types_enriched.get(LoadTypesRemote.SAVED_ARTISTS, set())
            if tracks:
                types_enriched.add(EnrichTypesRemote.TRACKS)
            self.types_enriched[LoadTypesRemote.SAVED_ARTISTS] = types_enriched
