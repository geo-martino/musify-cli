import os
from collections.abc import Collection
from functools import cached_property
from pathlib import Path

from aiorequestful.types import UnitCollection
from musify.libraries.core.collection import MusifyCollection
from musify.libraries.core.object import Track
from musify.libraries.local.library import LocalLibrary
from musify.libraries.local.playlist import LocalPlaylist, M3U
from musify.libraries.local.track import LocalTrack, SyncResultTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.logger import STAT
from musify.processors.base import Filter
from musify.utils import to_collection, get_user_input

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
    ## Backup/Restore
    ###########################################################################
    async def _load_library_for_backup(self) -> None:
        await self.load()

    async def _restore_library(self, path: Path) -> None:
        tags, tag_names = self._get_tags_to_restore_from_user()
        self.logger.print_line()

        await self.load(types=LoadTypesLocal.TRACKS)

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Restoring local track tags from backup: "
            f"{path.name} | Tags: {', '.join(tag_names)}\33[0m"
        )

        backup = self._load_json(path)
        tracks = {track["path"]: track for track in backup["tracks"]}

        self.library.restore_tracks(tracks, tags=tags)
        results = await self.library.save_tracks(tags=tags, replace=True, dry_run=self.dry_run)

        self.library.log_save_tracks_result(results)

    def _get_tags_to_restore_from_user(self) -> tuple[list[LocalTrackField], list[str]]:
        tags = LocalTrackField.ALL.to_tag()
        self.logger.info(f"\33[97mAvailable tags to restore: \33[94m{', '.join(tags)}\33[0m")
        message = "Select tags to restore separated by a space (entering nothing restores all available tags)"

        while True:  # get valid user input
            restore_tags = {t.casefold().strip() for t in get_user_input(message).split()}
            if not restore_tags:  # user entered nothing, restore all tags
                restore_tags = LocalTrackField.ALL.to_tag()
                break
            elif all(t in tags for t in restore_tags):  # input is valid
                break
            print(f"\33[91mTags entered were not recognised ({', '.join(restore_tags)}), try again\33[0m")

        return LocalTrackField.from_name(*restore_tags), list(restore_tags)

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

    async def set_tags(self) -> None:
        """Run all methods for setting and saving tags according to user-defined rules."""
        self.logger.debug("Set tag rules: START")

        await self.load(types=LoadTypesLocal.TRACKS)

        # noinspection PyTypeChecker
        results: dict[LocalTrack, SyncResultTrack] = await self.config.tags.run(
            self.library, updater=self.config.updater, dry_run=self.dry_run
        )

        if results:
            self.logger.print_line(STAT)
        self.library.log_save_tracks_result(results, log_values=True)
        log_prefix = "Would have set" if self.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        self.logger.debug("Set tag rules: DONE")

    ###########################################################################
    ## Playlists
    ###########################################################################
    async def merge_playlists(self, playlist_filter: Filter[str | LocalPlaylist]) -> None:
        """Merge playlists from a given folder with the currently loaded set of local playlists."""
        self.logger.debug("Merge playlists: START")

        if not (merge_folder_env := os.getenv("MUSIFY__LOCAL__PLAYLIST_MERGE")):
            self.logger.debug("Merge path not set. Set env var: 'MUSIFY__LOCAL__PLAYLIST_MERGE'")
            self.logger.debug("Merge playlists: DONE")
            return

        await self.load(types=[LoadTypesLocal.TRACKS, LoadTypesLocal.PLAYLISTS])

        merge_folder = Path(merge_folder_env)
        reference_folder = None
        if reference_folder_env := os.getenv("MUSIFY__LOCAL__PLAYLIST_REFERENCE"):
            reference_folder = Path(reference_folder_env)

        merge_library = LocalLibrary(
            playlist_folder=merge_folder,
            playlist_filter=playlist_filter,
            path_mapper=self.library.path_mapper,
            remote_wrangler=self.library.remote_wrangler,
            name="Merge",
        )
        merge_library.extend(self.library)

        reference_library = None
        if reference_folder is not None:
            reference_library = LocalLibrary(
                playlist_folder=reference_folder,
                playlist_filter=playlist_filter,
                path_mapper=self.library.path_mapper,
                remote_wrangler=self.library.remote_wrangler,
                name="Reference",
            )
            reference_library.extend(self.library)

        original_playlists = playlist_filter(self.library.playlists.values())

        log = (
            f"\33[1;95m ->\33[1;97m Merging {len(original_playlists)} local playlists with "
            f"{len(merge_library._playlist_paths)} merge playlists from \33[1;94m{merge_folder}\33[0m"
        )
        if reference_folder is not None:
            log += (
                f"\33[1;97m against {len(reference_library._playlist_paths)} reference playlists from "
                f"\33[1;94m{reference_folder}\33[0m"
            )
        self.logger.info(log)

        await merge_library.load_playlists()
        merge_library.log_playlists()

        if reference_library is not None:
            await reference_library.load_playlists()
            reference_library.log_playlists()

            deleted_playlists = set(reference_library.playlists).difference(merge_library.playlists)
            deleted_playlists.update(set(reference_library.playlists).difference(self.library.playlists))

            for name in deleted_playlists:
                if (pl := self.library.playlists.get(name)) is not None:
                    # noinspection PyAsyncCall
                    self.library.playlists.pop(pl.name)
                    os.remove(pl.path)
                if (pl := merge_library.playlists.get(name)) is not None:
                    # noinspection PyAsyncCall
                    merge_library.playlists.pop(pl.name)
                    os.remove(pl.path)

        self.library.merge_playlists(merge_library, reference=reference_library)
        self.logger.info(
            f"\33[1;95m >\33[1;97m Saving {len(self.library.playlists)} local playlists"
        )
        await self.library.save_playlists(dry_run=self.dry_run)
        await merge_library.save_playlists(dry_run=self.dry_run)

        self.logger.debug("Merge playlists: DONE")

    async def export_playlists(self, output_folder: Path, playlist_filter: Filter[str | LocalPlaylist] = ()) -> None:
        """Export a static copy of all local library playlists as M3U files."""
        self.logger.debug("Export playlists: START")

        await self.load(types=[LoadTypesLocal.TRACKS, LoadTypesLocal.PLAYLISTS])

        if staging_folder_env := os.getenv("MUSIFY__LOCAL__PLAYLIST_EXPORT"):
            staging_folder = Path(staging_folder_env)
            staging_folder.mkdir(parents=True, exist_ok=True)
        else:
            staging_folder = output_folder.joinpath("playlists")

        playlists = playlist_filter(self.library.playlists.values())

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Exporting a static copy of {len(playlists)} local playlists to "
            f"\33[1;94m{staging_folder}\33[0m"
        )

        async def _export_playlist(pl: LocalPlaylist) -> None:
            static_copy = M3U(
                path=staging_folder.joinpath(f"{pl.filename}.m3u"),
                path_mapper=pl.path_mapper,
                remote_wrangler=pl.remote_wrangler
            )
            static_copy.extend(pl.tracks)
            await static_copy.save(dry_run=self.dry_run)

        await self.logger.get_asynchronous_iterator(
            map(_export_playlist, playlists), desc="Exporting playlists", unit="playlists",
        )

        self.logger.debug("Export playlists: DONE")
