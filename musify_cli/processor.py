"""
Meta-functionality for the program.

Uses the :py:class:`MusifyManager` to run complex operations on various Musify objects.
"""
import json
import logging
import os
import re
import sys
from collections.abc import Mapping, Callable, Iterable
from copy import copy
from pathlib import Path
from time import perf_counter
from typing import Any, AsyncContextManager, Self

from jsonargparse import Namespace
from musify.libraries.core.object import Library
from musify.libraries.local.collection import LocalFolder
from musify.libraries.local.playlist import M3U, LocalPlaylist, PLAYLIST_CLASSES
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.object import RemotePlaylist
from musify.libraries.remote.core.types import RemoteObjectType
from musify.logger import MusifyLogger, STAT
from musify.processors.base import DynamicProcessor, dynamicprocessormethod
from musify.utils import get_user_input

from musify_cli.log.handlers import CurrentTimeRotatingFileHandler
from musify_cli.manager import MusifyManager
from musify_cli.manager.library import LocalLibraryManager, RemoteLibraryManager
from musify_cli.parser import LoadTypesRemote, EnrichTypesRemote, LoadTypesLocal


class MusifyProcessor(DynamicProcessor, AsyncContextManager):
    """Core functionality and meta-functions for the program"""

    @property
    def time_taken(self) -> float:
        """The total time taken since initialisation"""
        return perf_counter() - self._start_time

    @property
    def local(self) -> LocalLibraryManager:
        """The configuration for the :py:class:`LocalLibrary`"""
        return self.manager.local

    @property
    def remote(self) -> RemoteLibraryManager:
        """The configuration for the :py:class:`RemoteLibrary`"""
        return self.manager.remote

    def __init__(self, manager: MusifyManager):
        self._start_time = perf_counter()  # for measuring total runtime
        super().__init__()

        self.manager = manager

        # noinspection PyTypeChecker
        self.logger: MusifyLogger = logging.getLogger(__name__)
        sys.excepthook = self._handle_exception

        # ensure the config and file handler are using the same timestamp
        # clean up app data backup folder using the same logic for all file handlers
        for name in logging.getHandlerNames():
            handler = logging.getHandlerByName(name)
            if isinstance(handler, CurrentTimeRotatingFileHandler):
                self.manager.dt = handler.dt
                handler.rotator(str(self.manager.paths.backup.joinpath("{}")), self.manager.paths.backup)

        self.logger.debug(f"{self.__class__.__name__} initialised. Time taken: {self.time_taken:.3f}")

    def __await__(self):
        return self.run().__await__()

    async def __aenter__(self) -> Self:
        await self.manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.manager.__aexit__(exc_type, exc_val, exc_tb)

    async def run(self) -> Any:
        """Run the processor and any pre-/post-operations around it."""
        self.logger.debug(f"Called processor '{self._processor_name}': START")
        await super().__call__()
        self.logger.debug(f"Called processor '{self._processor_name}': DONE\n")

    def set_processor(self, name: str, config: Namespace = None) -> Callable[[], None]:
        """Set the processor to use from the given name"""
        name = name.replace("-", "_")
        self._set_processor_name(name)

        if config is not None:
            self.manager.set_config(config)

        return self._processor_method

    def _handle_exception(self, exc_type, exc_value, exc_traceback) -> None:
        """Custom exception handler. Handles exceptions through logger."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        self.logger.critical(
            "CRITICAL ERROR: Uncaught Exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    def _save_json(self, path: str | Path, data: Mapping[str, Any]) -> None:
        """Save a JSON file to a given folder, or this run's folder if not given"""
        path = Path(path).with_suffix(".json")

        with open(path, "w") as file:
            json.dump(data, file, indent=2)

        self.logger.info(f"\33[1;95m  >\33[1;97m Saved JSON file: \33[1;92m{path}\33[0m")

    def _load_json(self, path: Path) -> dict[str, Any]:
        """Load a stored JSON file from a given folder, or this run's folder if not given"""
        path = Path(path).with_suffix(".json")

        with open(path, "r") as file:
            data = json.load(file)

        self.logger.info(f"\33[1;95m  >\33[1;97m Loaded JSON file: \33[1;92m{path}\33[0m")
        return data

    def as_dict(self) -> dict[str, Any]:
        return {}

    ###########################################################################
    ## Utilities
    ###########################################################################
    @dynamicprocessormethod
    async def print(self) -> None:
        """Pretty print data from API getting input from user"""
        await self.remote.api.print_collection()

    @staticmethod
    def set_compilation_tags(collections: Iterable[LocalFolder]) -> None:
        """Modify tags for tracks in the given compilation ``collections``"""
        for collection in collections:
            tracks = sorted(collection.tracks, key=lambda x: str(x.path).casefold())
            album = " - ".join(collection.name.split(os.path.sep))

            for i, track in enumerate(tracks, 1):  # set tags
                track.album = album
                track.album_artist = "Various"
                track.track_number = i
                track.track_total = len(tracks)
                track.disc_number = 1
                track.disc_total = 1
                track.compilation = True

    ###########################################################################
    ## Backup/Restore
    ###########################################################################
    def _library_backup_name(self, library: Library, key: str | None = None) -> str:
        """The identifier to use in filenames of the :py:class:`Library`"""
        name = f"{library.__class__.__name__} - {self.local.library.name}"
        if key:
            name = f"[{key.upper()}] - {name}"
        return name

    @dynamicprocessormethod
    async def backup(self) -> None:
        """Backup data for all tracks and playlists in all libraries"""
        self.logger.debug("Backup libraries: START")

        key = self.manager.backup_key
        if not key:
            key = get_user_input("Enter a key for this backup. Hit return to backup without a key")
            self.logger.print_line()

        await self.local.load()
        await self.remote.load(types=[LoadTypesRemote.playlists, LoadTypesRemote.saved_tracks])

        local_backup_path = Path(self.manager.paths.backup, self._library_backup_name(self.local.library, key))
        self._save_json(local_backup_path, self.local.library.json())
        remote_backup_path = Path(self.manager.paths.backup, self._library_backup_name(self.remote.library, key))
        self._save_json(remote_backup_path, self.remote.library.json())

        self.logger.debug("Backup libraries: DONE")

    @dynamicprocessormethod
    async def restore(self) -> None:
        """Restore library data from a backup, getting user input for the settings"""
        backup_folder = self.manager.paths.backup.parent
        available_groups = self._get_available_backup_groups(backup_folder)

        if len(available_groups) == 0:
            self.logger.info("\33[93mNo backups found, skipping.\33[0m")
            return

        restore_dir = self._get_restore_dir_from_user(backup_folder=backup_folder, available_groups=available_groups)
        restore_key = self._get_restore_key_from_user(restore_dir)

        restored = []
        if get_user_input(f"Restore {self.local.source} library tracks? (enter 'y')").casefold() == 'y':
            await self._restore_local(restore_dir, key=restore_key)
            restored.append(self.local.library.name)
            self.logger.print_line()
        if get_user_input(f"Restore {self.remote.source} library playlists? (enter 'y')").casefold() == 'y':
            await self._restore_spotify(restore_dir, key=restore_key)
            restored.append(self.remote.source)

        if not restored:
            self.logger.info("\33[90mNo libraries restored.\33[0m")
            return
        self.logger.info(f"\33[92mSuccessfully restored libraries: {", ".join(restored)}\33[0m")

    def _get_available_backup_groups(self, backup_folder: Path) -> list[str]:
        backup_names = (self._library_backup_name(self.local.library), self._library_backup_name(self.remote.library))

        available_backups: list[str] = []  # names of the folders which contain usable backups
        for parent, _, filenames in backup_folder.walk():
            if parent == backup_folder:  # skip current run's data
                continue
            group = parent.relative_to(backup_folder).name  # backup group is the folder name

            for file in map(Path, filenames):
                if group in available_backups:
                    break
                for name in backup_names:
                    if name in file.stem:
                        available_backups.append(group)
                        break

        return available_backups

    def _get_restore_dir_from_user(self, backup_folder: Path, available_groups: list[str]) -> Path:
        self.logger.info(
            "\33[97mAvailable backups: \n\t\33[97m- \33[94m{}\33[0m"
            .format("\33[0m\n\t\33[97m-\33[0m \33[94m".join(available_groups))
        )

        while True:  # get valid user input
            group = get_user_input("Select the backup to use")
            if group in available_groups:  # input is valid
                break
            print(f"\33[91mBackup '{group}' not recognised, try again\33[0m")

        return backup_folder.joinpath(group)

    def _get_restore_key_from_user(self, path: Path):
        available_keys = {re.sub(r"^\[(\w+)].*", "\\1", file) for file in os.listdir(path)}

        self.logger.info(
            "\33[97mAvailable backup keys: \n\t\33[97m- \33[94m{}\33[0m"
            .format("\33[0m\n\t\33[97m-\33[0m \33[94m".join(available_keys))
        )
        available_keys = {key.casefold() for key in available_keys}

        while True:  # get valid user input
            key = get_user_input("Select the backup type to use")
            if key.casefold() in available_keys:  # input is valid
                break
            print(f"\33[91mBackup '{key}' not recognised, try again\33[0m")

        return key

    async def _restore_local(self, path: Path, key: str | None = None) -> None:
        """Restore local library data from a backup, getting user input for the settings"""
        self.logger.debug("Restore local: START")
        self.logger.print_line()

        tags, tag_names = self._get_tags_to_restore_from_user()

        self.logger.print_line()
        await self.local.load(types=LoadTypesLocal.tracks)

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Restoring local track tags from backup: "
            f"{path.name} | Tags: {', '.join(tag_names)}\33[0m"
        )
        backup_path = Path(self.manager.paths.backup, self._library_backup_name(self.local.library, key))
        backup = self._load_json(backup_path)

        # restore and save
        tracks = {track["path"]: track for track in backup["tracks"]}
        self.local.library.restore_tracks(tracks, tags=tags)
        results = await self.local.library.save_tracks(tags=tags, replace=True, dry_run=self.manager.dry_run)

        self.local.library.log_save_tracks_result(results)
        self.logger.debug("Restore local: DONE")

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

    async def _restore_spotify(self, path: Path, key: str | None = None) -> None:
        """Restore remote library data from a backup, getting user input for the settings"""
        self.logger.debug(f"Restore {self.remote.source}: START")
        self.logger.print_line()

        await self.remote.load(types=[LoadTypesRemote.saved_tracks, LoadTypesRemote.playlists])

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Restoring {self.remote.source} playlists from backup: {path.name} \33[0m"
        )
        backup_path = Path(self.manager.paths.backup, self._library_backup_name(self.remote.library, key))
        backup = self._load_json(backup_path)

        # restore and sync
        await self.remote.library.restore_playlists(backup["playlists"])
        results = await self.remote.library.sync(kind="refresh", reload=False, dry_run=self.manager.dry_run)

        self.remote.library.log_sync(results)
        self.logger.debug(f"Restore {self.remote.source}: DONE")

    ###########################################################################
    ## Report/Search functions
    ###########################################################################
    @dynamicprocessormethod
    async def report(self) -> None:
        """Produce various reports on loaded data"""
        self.logger.debug("Generate reports: START")
        await self.manager.reports
        self.logger.debug("Generate reports: DONE")

    @dynamicprocessormethod
    async def check(self) -> None:
        """Run check on entire library by album and update URI tags on file"""
        self.logger.debug("Check and update URIs: START")

        await self.local.load(types=LoadTypesLocal.tracks)

        folders = self.manager.filter(self.local.library.folders)
        if not await self.remote.check(folders):
            self.logger.debug("Check and update URIs: DONE")
            return

        self.logger.info(f"\33[1;95m ->\33[1;97m Updating tags for {len(self.local.library)} tracks: uri \33[0m")
        results = await self.local.library.save_tracks(
            tags=LocalTrackField.URI, replace=True, dry_run=self.manager.dry_run
        )

        if results:
            self.logger.print_line(STAT)
        self.local.library.log_save_tracks_result(results)
        self.logger.info(f"\33[92mSet tags for {len(results)} tracks \33[0m")

        self.logger.debug("Check and update URIs: DONE")

    @dynamicprocessormethod
    async def search(self) -> None:
        """Run all methods for searching, checking, and saving URI associations for local files."""
        self.logger.debug("Search and match: START")

        await self.local.load(types=LoadTypesLocal.tracks)

        albums = self.local.library.albums
        [album.items.remove(track) for album in albums for track in album.items.copy() if track.has_uri is not None]
        [albums.remove(album) for album in albums.copy() if len(album.items) == 0]

        if len(albums) == 0:
            self.logger.info("\33[1;95m ->\33[0;90m All items matched or unavailable. Skipping search.\33[0m")
            self.logger.print_line()
            return

        await self.remote.search(albums)
        if not await self.remote.check(albums):
            self.logger.debug("Search and match: DONE")
            return

        await self.remote.library.extend([track for album in albums for track in album], allow_duplicates=False)
        await self.remote.library.enrich_tracks(features=True, albums=True, artists=True)

        self.local.merge_tracks(self.remote.library)
        results = await self.local.save_tracks_in_collections(collections=albums, replace=True)

        if results:
            self.logger.print_line(STAT)
        self.local.library.log_save_tracks_result(results)
        log_prefix = "Would have set" if self.manager.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        self.logger.debug("Search and match: DONE")

    ###########################################################################
    ## Local-bound library operations
    ###########################################################################
    @dynamicprocessormethod
    async def pull_tags(self) -> None:
        """Run all methods for pulling tag data from remote and updating local track tags"""
        self.logger.debug("Update tags: START")

        await self.local.load(types=LoadTypesLocal.tracks)
        await self.remote.library.extend(self.local.library, allow_duplicates=False)
        await self.remote.library.enrich_tracks(features=True, albums=True, artists=True)

        self.local.merge_tracks(self.remote.library)
        results = await self.local.save_tracks()

        if results:
            self.logger.print_line(STAT)
        self.local.library.log_save_tracks_result(results)
        log_prefix = "Would have set" if self.manager.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        self.logger.debug("Update tags: DONE")

    @dynamicprocessormethod
    async def process_compilations(self) -> None:
        """Run all methods for setting and saving local track tags for compilation albums"""
        self.logger.debug("Update compilations: START")

        await self.local.load(types=LoadTypesLocal.tracks)

        folders = self.manager.filter(self.local.library.folders)

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Setting compilation style tags "
            f"for {sum(len(folder) for folder in folders)} tracks in {len(folders)} folders\n"
        )
        self.set_compilation_tags(folders)
        results = await self.local.save_tracks_in_collections(collections=folders)

        if results:
            self.logger.print_line(STAT)
        self.local.library.log_save_tracks_result(results)
        log_prefix = "Would have set" if self.manager.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        self.logger.debug("Update compilations: DONE")

    @dynamicprocessormethod
    async def merge_playlists(self) -> None:
        """Merge playlists from a given folder with the currently loaded set of local playlists."""
        self.logger.debug("Merge playlists: START")

        if not (merge_folder := os.getenv("MUSIFY__LOCAL__PLAYLIST_EXPORT")):
            self.logger.debug("Merge path not set. Set env var: 'MUSIFY__LOCAL__PLAYLIST_EXPORT'")
            self.logger.debug("Merge playlists: DONE")
            return

        await self.local.load(types=[LoadTypesLocal.tracks, LoadTypesLocal.playlists])

        merge_folder = Path(merge_folder)
        merge_playlists: list[LocalPlaylist] = []
        for cls in PLAYLIST_CLASSES:
            merge_playlists.extend(
                cls(path, path_mapper=self.local.path_mapper, remote_wrangler=self.remote.wrangler)
                for path in cls.get_filepaths(merge_folder)
            )

        original_playlists = self.manager.filter(self.local.library.playlists.values())
        merge_playlists = self.manager.filter(merge_playlists)
        self.logger.info(
            f"\33[1;95m ->\33[1;97m Merging {len(original_playlists)} local playlists with "
            f"{len(merge_playlists)} merge playlists from \33[1;94m{merge_folder}\33[0m"
        )

        for merge_pl in merge_playlists:
            name = merge_pl.name
            if merge_pl.name not in self.local.library.playlists:
                print(name, merge_pl.path, merge_pl.path.stem, merge_pl.path.name)
                continue

            original_pl = self.local.library.playlists[name]
            await merge_pl.load(self.local.library)
            print(name, len(merge_pl), len(original_pl), len(merge_pl) == len(original_pl))

        self.logger.debug("Merge playlists: DONE")

    @dynamicprocessormethod
    async def export_playlists(self) -> None:
        """Export a static copy of all local library playlists as M3U files."""
        self.logger.debug("Export playlists: START")

        await self.local.load(types=[LoadTypesLocal.tracks, LoadTypesLocal.playlists])

        if staging_folder_env := os.getenv("MUSIFY__LOCAL__PLAYLIST_EXPORT"):
            staging_folder = Path(staging_folder_env)
            staging_folder.mkdir(parents=True, exist_ok=True)
        else:
            staging_folder = self.manager.paths.local_library.joinpath("playlists")

        playlists = self.manager.filter(self.local.library.playlists.values())
        self.logger.info(
            f"\33[1;95m ->\33[1;97m Exporting a static copy of {len(playlists)} local playlists to "
            f"\33[1;94m{staging_folder}\33[0m"
        )

        async def _export_playlist(pl: LocalPlaylist) -> None:
            static_copy = M3U(
                path=staging_folder.joinpath(pl.filename).with_suffix(".m3u"),
                path_mapper=pl.path_mapper,
                remote_wrangler=pl.remote_wrangler
            )
            static_copy.extend(pl.tracks)
            await static_copy.save(dry_run=self.manager.dry_run)

        await self.logger.get_asynchronous_iterator(
            map(_export_playlist, playlists), desc="Exporting playlists", unit="playlists",
        )

        self.logger.debug("Export playlists: DONE")

    ###########################################################################
    ## Remote-bound library operations
    ###########################################################################
    @dynamicprocessormethod
    async def sync_remote(self) -> None:
        """Run all main functions for synchronising remote playlists with a local library"""
        self.logger.debug(f"Sync {self.remote.source}: START")

        await self.local.load()
        await self.remote.load(types=LoadTypesRemote.playlists)

        playlists = [copy(pl) for pl in self.local.library.playlists.values()]
        for pl in playlists:  # so filter_playlists doesn't clear the list of tracks on the original playlist objects
            pl._tracks = pl.tracks.copy()

        results = await self.remote.sync(playlists)

        self.remote.library.log_sync(results)
        self.logger.debug(f"Sync {self.remote.source}: DONE")

    @dynamicprocessormethod
    async def download(self) -> None:
        """Run the :py:class:`ItemDownloadHelper`"""
        self.logger.debug("Download helper: START")

        responses = self.remote.api.user_playlist_data
        playlists: list[RemotePlaylist] = self.manager.filter(list(map(
            lambda response: self.remote.factory.playlist(response, skip_checks=True), responses.values()
        )))
        await self.remote.api.get_items(playlists, kind=RemoteObjectType.PLAYLIST)

        self.manager.run_download_helper(playlists)

        self.logger.debug("Download helper: DONE")

    @dynamicprocessormethod
    async def new_music(self) -> None:
        """Create a playlist of new music released by user's followed artists"""
        self.logger.debug("New music playlist: START")

        # load saved artists and their albums with fresh data
        load_albums = any([
            LoadTypesRemote.saved_artists not in self.remote.types_loaded,
            EnrichTypesRemote.albums not in self.remote.types_enriched.get(LoadTypesRemote.saved_artists, [])
        ])
        if load_albums:
            await self.remote.load(types=[LoadTypesRemote.saved_artists])
            await self.remote.library.enrich_saved_artists(types=("album", "single"))

        albums_to_extend = [
            album for artist in self.remote.library.artists for album in artist.albums
            if len(album.tracks) < album.track_total
        ]
        await self.manager.extend_albums(albums_to_extend)

        # log load results
        if load_albums or albums_to_extend:
            self.logger.print_line(STAT)
            self.remote.library.log_artists()
            self.logger.print_line()

        new_albums = self.manager.get_new_artist_albums()
        name, results = await self.manager.create_new_music_playlist(new_albums)

        self.logger.print_line(STAT)
        self.remote.library.log_sync({name: results})
        log_prefix = "Would have added" if self.manager.dry_run else "Added"
        self.logger.info(f"\33[92m{log_prefix} {results.added} new tracks to playlist: '{name}' \33[0m")

        self.logger.debug("New music playlist: DONE")
