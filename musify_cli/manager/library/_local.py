from collections.abc import Collection
from functools import cached_property

from musify.libraries.core.collection import MusifyCollection
from musify.libraries.core.object import Track
from musify.libraries.local.collection import BasicLocalCollection
from musify.libraries.local.library import LocalLibrary
from musify.libraries.local.track import LocalTrack, SyncResultTrack
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.logger import STAT
from musify.types import UnitCollection
from musify.utils import to_collection

from musify_cli.config.library.local import LocalLibraryConfig
from musify_cli.config.library.types import LoadTypesLocal
from musify_cli.manager.library._core import LibraryManager


class LocalLibraryManager[L: LocalLibrary, C: LocalLibraryConfig](LibraryManager[L, C]):
    """Instantiates and manages a generic :py:class:`LocalLibrary` and related objects from a given ``config``."""

    def __init__(self, config: LocalLibraryConfig, dry_run: bool = True, remote_wrangler: RemoteDataWrangler = None):
        super().__init__(config=config, dry_run=dry_run)

        self._remote_wrangler = remote_wrangler

        self.types_loaded: set[LoadTypesLocal] = set()

    @cached_property
    def library(self):
        self.initialised = True
        return self.config.create(self._remote_wrangler)

    ###########################################################################
    ## Operations
    ###########################################################################
    async def load(self, types: UnitCollection[LoadTypesLocal] = (), force: bool = False) -> None:
        def _should_load(load_type: LoadTypesLocal) -> bool:
            selected = not types or load_type in types
            can_be_loaded = force or load_type not in self.types_loaded
            return selected and can_be_loaded

        types = to_collection(types)

        if types and self.types_loaded.intersection(types) == set(types) and not force:
            return
        elif not types and (force or not self.types_loaded):
            await self.library.load()
            self.types_loaded.update(LoadTypesLocal.all())
            return

        loaded = set()
        if _should_load(LoadTypesLocal.TRACKS):
            await self.library.load_tracks()
            self.types_loaded.add(LoadTypesLocal.TRACKS)
            loaded.add(LoadTypesLocal.TRACKS)
        if _should_load(LoadTypesLocal.PLAYLISTS):
            await self.library.load_playlists()
            self.types_loaded.add(LoadTypesLocal.PLAYLISTS)
            loaded.add(LoadTypesLocal.PLAYLISTS)

        if not loaded:
            return

        self.logger.print_line(STAT)
        if LoadTypesLocal.TRACKS in loaded:
            self.library.log_tracks()
        if LoadTypesLocal.PLAYLISTS in loaded:
            self.library.log_playlists()
        self.logger.print_line()

    async def save_tracks(
            self, collections: UnitCollection[MusifyCollection[LocalTrack]] | None = None,
    ) -> dict[LocalTrack, SyncResultTrack]:
        """
        Saves the tags of all tracks in the given ``collections``.

        :param collections: The collections containing the tracks which you wish to save.
        :return: A map of the :py:class:`LocalTrack` saved to its result as a :py:class:`SyncResultTrack` object
        """
        if collections is None:
            collections = self.library

        return await self.config.updater.run(collection=collections, dry_run=self.dry_run)

    def merge_tracks(self, tracks: Collection[Track]) -> None:
        """
        Merge this collection with another collection or list of items
        by performing an inner join on the pre-configured set of tags.

        :param tracks: List of items or :py:class:`MusifyCollection` to merge with.
        """
        self.library.merge_tracks(tracks, tags=self.config.updater.tags)
