from collections.abc import Collection

from jsonargparse import Namespace
from musify.file.path_mapper import PathMapper, PathStemMapper
from musify.libraries.core.object import Track
from musify.libraries.local.collection import LocalCollection
from musify.libraries.local.library import LocalLibrary, MusicBee
from musify.libraries.local.track import LocalTrack, SyncResultTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.processors.wrangle import RemoteDataWrangler
from musify.log import STAT
from musify.types import UnitIterable, UnitCollection
from musify.utils import to_collection

from musify_cli.manager.library._core import LibraryManager
from musify_cli.parser import LoadTypesLocal


class LocalLibraryManager(LibraryManager):
    """Instantiates and manages a generic :py:class:`LocalLibrary` and related objects from a given ``config``."""

    def __init__(self, name: str, config: Namespace, dry_run: bool = True):
        super().__init__(name=name, config=config, dry_run=dry_run)

        self._library: LocalLibrary | None = None

        # utilities
        self._remote_wrangler: RemoteDataWrangler | None = None

        self.types_loaded: set[LoadTypesLocal] = set()

    @property
    def source(self) -> str:
        return str(LocalLibrary.source)

    @property
    def _path_mapper(self) -> PathMapper:
        """The configured :py:class:`PathMapper` to use when instantiating a library"""
        return PathStemMapper(stem_map=self.config.paths.map)

    @property
    def library(self) -> LocalLibrary:
        """The initialised local library"""
        if self._library is None:
            self._library = LocalLibrary(
                library_folders=self.config.paths.library.paths,
                playlist_folder=self.config.paths.playlists,
                playlist_filter=self.playlist_filter or (),
                path_mapper=self._path_mapper,
                remote_wrangler=self._remote_wrangler,
            )
            self.initialised = True

        return self._library

    ###########################################################################
    ## Operations
    ###########################################################################
    async def load(self, types: UnitCollection[LoadTypesLocal] = (), force: bool = False) -> None:
        def _check_loaded(load_type: LoadTypesLocal) -> bool:
            return load_type in self.types_loaded

        def _check_load(load_type: LoadTypesLocal) -> bool:
            selected = not types or load_type in types
            can_be_loaded = force or not _check_loaded(load_type)
            return selected and can_be_loaded

        types = to_collection(types)

        if types and self.types_loaded.intersection(types) == set(types) and not force:
            return
        elif not types and (force or not self.types_loaded):
            await self.library.load()
            self.types_loaded.update(LoadTypesLocal.all())
            return

        if _check_load(LoadTypesLocal.tracks):
            await self.library.load_tracks()
            self.types_loaded.add(LoadTypesLocal.tracks)
        if _check_load(LoadTypesLocal.playlists):
            await self.library.load_playlists()
            self.types_loaded.add(LoadTypesLocal.playlists)

        self.logger.print(STAT)
        if _check_loaded(LoadTypesLocal.tracks):
            self.library.log_tracks()
        if _check_loaded(LoadTypesLocal.playlists):
            self.library.log_playlists()
        self.logger.print()

    async def save_tracks(self) -> dict[LocalTrack, SyncResultTrack]:
        """
        Saves the tags of all tracks in this library.

        :return: A map of the :py:class:`LocalTrack` saved to its result as a :py:class:`SyncResultTrack` object
        """
        tags = self.config.updater.tags
        replace = self.config.updater.replace

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Updating tags for {len(self.library)} tracks: "
            f"{', '.join(t.name.lower() for t in tags)} \33[0m"
        )
        return await self.library.save_tracks(tags=tags, replace=replace, dry_run=self.dry_run)

    async def save_tracks_in_collections(
            self,
            collections: UnitIterable[LocalCollection[LocalTrack]] | None = None,
            tags: UnitIterable[LocalTrackField] = None,
            replace: bool = None,
    ) -> dict[LocalTrack, SyncResultTrack]:
        """
        Saves the tags of all tracks in the given ``collections``.

        :param collections: The collections containing the tracks which you wish to save.
        :param tags: Tags to be updated.
        :param replace: Destructively replace tags in each file.
        :return: A map of the :py:class:`LocalTrack` saved to its result as a :py:class:`SyncResultTrack` object
        """
        tags = to_collection(tags) or self.config.updater.tags
        replace = replace if replace is not None else self.config.updater.replace

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Updating tags "
            f"for {sum(len(coll) for coll in collections)} tracks in {len(collections)} collections\n"
            f"\33[0;90m    Tags: {', '.join(t.name.lower() for t in tags)} \33[0m"
        )

        collections = to_collection(collections)
        bar = self.logger.get_iterator(collections, desc="Updating tracks", unit="tracks")
        return {
            track: await track.save(tags=tags, replace=replace, dry_run=self.dry_run)
            for coll in bar for track in coll
        }

    def merge_tracks(self, tracks: Collection[Track]) -> None:
        """
        Merge this collection with another collection or list of items
        by performing an inner join on the pre-configured set of tags.

        :param tracks: List of items or :py:class:`MusifyCollection` to merge with.
        """
        self.library.merge_tracks(tracks, tags=self.config.updater.tags)


class MusicBeeManager(LocalLibraryManager):
    """Instantiates and manages a :py:class:`MusicBee` library and related objects from a given ``config``."""

    @property
    def source(self) -> str:
        return str(MusicBee.source)

    @property
    def library(self) -> MusicBee:
        if self._library is None:
            self._library = MusicBee(
                musicbee_folder=self.config.paths.library.paths,
                playlist_filter=self.config.playlists.filter or (),
                path_mapper=self._path_mapper,
                remote_wrangler=self._remote_wrangler,
            )
            self.initialised = True

        return self._library
