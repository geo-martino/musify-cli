"""
Meta-functionality for the program.

Uses the :py:class:`MusifyManager` to run complex operations on various Musify objects.
"""
import json
import logging
import os
import re
import sys
from collections.abc import Mapping, Callable, Collection, Iterable
from copy import copy
from os.path import basename, dirname, join, relpath, splitext, sep
from time import perf_counter
from typing import Any

from musify.libraries.core.object import Library
from musify.libraries.local.collection import LocalFolder
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.enum import RemoteObjectType
from musify.libraries.remote.core.object import RemotePlaylist
from musify.log import STAT
from musify.log.handlers import CurrentTimeRotatingFileHandler
from musify.log.logger import MusifyLogger
from musify.processors.base import DynamicProcessor, dynamicprocessormethod
from musify.utils import get_user_input, get_max_width, align_string

from musify_cli.manager import MusifyManager
from musify_cli.manager.library import LocalLibraryManager, RemoteLibraryManager
from musify_cli.parser import LoadTypesRemote, EnrichTypesRemote, LoadTypesLocal


class MusifyProcessor(DynamicProcessor):
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
        # clean up output folder using the same logic for all file handlers
        for name in logging.getHandlerNames():
            handler = logging.getHandlerByName(name)
            if isinstance(handler, CurrentTimeRotatingFileHandler):
                self.manager.dt = handler.dt
                handler.rotator(join(dirname(self.manager.output_folder), "{}"), self.manager.output_folder)

        self.logger.debug(f"{self.__class__.__name__} initialised. Time taken: {self.time_taken:.3f}")

    def __call__(self, *args, **kwargs) -> Any:
        self.logger.debug(f"Called processor '{self._processor_name}': START")

        self.manager.run_pre()
        super().__call__(*args, **kwargs)
        self.manager.run_post()

        self.logger.debug(f"Called processor '{self._processor_name}': DONE\n")

    def set_processor(self, name: str) -> Callable[[], None]:
        """Set the processor to use from the given name"""
        name = name.replace("-", "_")
        self._set_processor_name(name)
        return self._processor_method

    def _handle_exception(self, exc_type, exc_value, exc_traceback) -> None:
        """Custom exception handler. Handles exceptions through logger."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        self.logger.critical(
            "CRITICAL ERROR: Uncaught Exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    def _save_json(self, filename: str, data: Mapping[str, Any], folder: str | None = None) -> None:
        """Save a JSON file to a given folder, or this run's folder if not given"""
        if not filename.casefold().endswith(".json"):
            filename += ".json"
        folder = folder or self.manager.output_folder
        path = join(folder, filename)

        with open(path, "w") as file:
            json.dump(data, file, indent=2)

    def _load_json(self, filename: str, folder: str | None = None) -> dict[str, Any]:
        """Load a stored JSON file from a given folder, or this run's folder if not given"""
        if not filename.casefold().endswith(".json"):
            filename += ".json"
        folder = folder or self.manager.output_folder
        path = join(folder, filename)

        with open(path, "r") as file:
            data = json.load(file)

        return data

    def as_dict(self) -> dict[str, Any]:
        return {}

    ###########################################################################
    ## Utilities
    ###########################################################################
    @dynamicprocessormethod
    def print(self) -> None:
        """Pretty print data from API getting input from user"""
        self.remote.api.print_collection(use_cache=self.remote.use_cache)

    @staticmethod
    def set_compilation_tags(collections: Iterable[LocalFolder]) -> None:
        """Modify tags for tracks in the given compilation ``collections``"""
        for collection in collections:
            tracks = sorted(collection.tracks, key=lambda x: x.path)
            album = " - ".join(collection.name.split(sep))

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
    def backup(self) -> None:
        """Backup data for all tracks and playlists in all libraries"""
        self.logger.debug("Backup libraries: START")

        key = self.manager.backup_key
        if not key:
            key = get_user_input("Enter a key for this backup. Hit return to backup without a key")
        self.logger.print()

        self.local.load()
        self.remote.load(types=[LoadTypesRemote.playlists, LoadTypesRemote.saved_tracks])

        self._save_json(self._library_backup_name(self.local.library, key), self.local.library.json())
        self._save_json(self._library_backup_name(self.remote.library, key), self.remote.library.json())

        self.logger.debug("Backup libraries: DONE")

    @dynamicprocessormethod
    def restore(self) -> None:
        """Restore library data from a backup, getting user input for the settings"""
        output_parent = dirname(self.manager.output_folder)
        backup_names = (self._library_backup_name(self.local.library), self._library_backup_name(self.remote.library))

        available_backups: list[str] = []  # names of the folders which contain usable backups
        for path in os.walk(output_parent):
            if path[0] == output_parent:  # skip current run's data
                continue
            folder = str(relpath(path[0], output_parent))

            for file in path[2]:
                if folder in available_backups:
                    break
                for name in backup_names:
                    if name in splitext(file)[0]:
                        available_backups.append(folder)
                        break

        if len(available_backups) == 0:
            self.logger.info("\33[93mNo backups found, skipping.\33[0m")
            return

        self.logger.info(
            "\33[97mAvailable backups: \n\t\33[97m- \33[94m{}\33[0m"
            .format("\33[0m\n\t\33[97m-\33[0m \33[94m".join(available_backups))
        )

        while True:  # get valid user input
            restore_from = get_user_input("Select the backup to use")
            if restore_from in available_backups:  # input is valid
                break
            print(f"\33[91mBackup '{restore_from}' not recognised, try again\33[0m")
        restore_from = join(output_parent, restore_from)
        available_keys = [re.sub(r"^\[(\w+)].*", "\\1", file).casefold() for file in os.listdir(restore_from)]

        self.logger.info(
            "\33[97mAvailable backup keys: \n\t\33[97m- \33[94m{}\33[0m"
            .format("\33[0m\n\t\33[97m-\33[0m \33[94m".join(available_keys))
        )

        while True:  # get valid user input
            key = get_user_input("Select the backup type to use")
            if key.casefold() in available_keys:  # input is valid
                break
            print(f"\33[91mBackup '{key}' not recognised, try again\33[0m")

        restored = []
        if get_user_input(f"Restore {self.local.source} library tracks? (enter 'y')").casefold() == 'y':
            self._restore_local(restore_from, key=key)
            restored.append(self.local.library.name)
            self.logger.print()
        if get_user_input(f"Restore {self.remote.source} library playlists? (enter 'y')").casefold() == 'y':
            self._restore_spotify(restore_from, key=key)
            restored.append(self.remote.source)

        if not restored:
            self.logger.info("No libraries restored.")
            return
        self.logger.info(f"Successfully restored libraries: {", ".join(restored)}")

    def _restore_local(self, folder: str, key: str | None = None) -> None:
        """Restore local library data from a backup, getting user input for the settings"""
        self.logger.debug("Restore local: START")
        self.logger.print()

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

        self.logger.print()
        self.remote.load(types=LoadTypesRemote.saved_tracks)

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Restoring local track tags from backup: "
            f"{basename(folder)} | Tags: {', '.join(restore_tags)}\33[0m"
        )
        backup = self._load_json(self._library_backup_name(self.local.library, key), folder)

        # restore and save
        tracks = {track["path"]: track for track in backup["tracks"]}
        self.local.library.restore_tracks(tracks, tags=LocalTrackField.from_name(*restore_tags))
        results = self.local.library.save_tracks(tags=tags, replace=True, dry_run=self.manager.dry_run)

        self.local.library.log_save_tracks_result(results)
        self.logger.debug("Restore local: DONE")

    def _restore_spotify(self, folder: str, key: str | None = None) -> None:
        """Restore remote library data from a backup, getting user input for the settings"""
        self.logger.debug(f"Restore {self.remote.source}: START")
        self.logger.print()

        self.remote.load(types=[LoadTypesRemote.saved_tracks, LoadTypesRemote.playlists])

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Restoring {self.remote.source} playlists from backup: {basename(folder)} \33[0m"
        )
        backup = self._load_json(self._library_backup_name(self.remote.library, key), folder)

        # restore and sync
        self.remote.library.restore_playlists(backup["playlists"])
        results = self.remote.library.sync(kind="refresh", reload=False, dry_run=self.manager.dry_run)

        self.remote.library.log_sync(results)
        self.logger.debug(f"Restore {self.remote.source}: DONE")

    @dynamicprocessormethod
    def extract(self) -> None:
        """Extract and save images from local or remote items"""
        # TODO: add library-wide image extraction method
        raise NotImplementedError

    ###########################################################################
    ## Report/Search functions
    ###########################################################################
    @dynamicprocessormethod
    def report(self) -> None:
        """Produce various reports on loaded data"""
        self.logger.debug("Generate reports: START")
        self.manager.reports()
        self.logger.debug("Generate reports: DONE")

    @dynamicprocessormethod
    def check(self) -> None:
        """Run check on entire library by album and update URI tags on file"""
        def finalise() -> None:
            """Finalise function operation"""
            self.logger.print()
            self.logger.debug("Check and update URIs: DONE")

        self.logger.debug("Check and update URIs: START")
        self.local.load()

        folders = self.manager.filter(self.local.library.folders)
        if not self.remote.check(folders):
            finalise()
            return

        self.logger.info(f"\33[1;95m ->\33[1;97m Updating tags for {len(self.local.library)} tracks: uri \33[0m")
        results = self.local.library.save_tracks(tags=LocalTrackField.URI, replace=True, dry_run=self.manager.dry_run)

        if results:
            self.logger.print(STAT)
        self.local.library.log_save_tracks_result(results)
        self.logger.info(f"\33[92mSet tags for {len(results)} tracks \33[0m")

        finalise()

    @dynamicprocessormethod
    def search(self) -> None:
        """Run all methods for searching, checking, and saving URI associations for local files."""
        def finalise() -> None:
            """Finalise function operation"""
            self.logger.print()
            self.logger.debug("Search and match: DONE")

        self.logger.debug("Search and match: START")

        albums = self.local.library.albums
        [album.items.remove(track) for album in albums for track in album.items.copy() if track.has_uri is not None]
        [albums.remove(album) for album in albums.copy() if len(album.items) == 0]

        if len(albums) == 0:
            self.logger.info("\33[1;95m ->\33[0;90m All items matched or unavailable. Skipping search.\33[0m")
            self.logger.print()
            return

        self.remote.search(albums)
        if not self.remote.check(albums):
            finalise()
            return

        self.logger.info(f"\33[1;95m ->\33[1;97m Updating tags for {len(self.local.library)} tracks: uri \33[0m")
        results = self.local.save_tracks_in_collections(collections=albums, tags=LocalTrackField.URI, replace=True)

        if results:
            self.logger.print(STAT)
        self.local.library.log_save_tracks_result(results)
        log_prefix = "Would have set" if self.manager.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        finalise()

    ###########################################################################
    ## Miscellaneous library operations
    ###########################################################################
    @dynamicprocessormethod
    def pull_tags(self) -> None:
        """Run all methods for pulling tag data from remote and updating local track tags"""
        self.logger.debug("Update tags: START")

        self.local.load(types=LoadTypesLocal.tracks)
        self.remote.load(
            types=[LoadTypesRemote.saved_tracks, LoadTypesRemote.playlists],
            extend=self.local.library,
            enrich=True,
            enrich_types=EnrichTypesRemote.artists
        )

        self.local.merge_tracks(self.remote.library)
        results = self.local.save_tracks()

        if results:
            self.logger.print(STAT)
        self.local.library.log_save_tracks_result(results)
        log_prefix = "Would have set" if self.manager.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        # TODO: why do some unavailable tracks keep getting updated? (this may be resolved now...?)
        #  This block is for debugging
        max_width = get_max_width([track.path for track in results], max_width=80)
        for track, result in results.items():
            self.logger.stat(
                f"\33[97m{align_string(track.path, max_width=max_width, truncate_left=True)} \33[0m| " +
                f"\33[94m{' - '.join(
                    f"{tag.name, condition, (track[tag.name.lower()] if hasattr(track, tag.name.lower()) else "img?")}"
                    for tag, condition in result.updated.items()
                )
                } \33[0m"
            )

        self.logger.print()
        self.logger.debug("Update tags: DONE")

    @dynamicprocessormethod
    def process_compilations(self) -> None:
        """Run all methods for setting and updating local track tags for compilation albums"""
        self.logger.debug("Update compilations: START")

        self.local.load(types=LoadTypesLocal.tracks)

        folders = self.manager.filter(self.local.library.folders)

        self.logger.info(
            f"\33[1;95m ->\33[1;97m Setting compilation style tags "
            f"for {sum(len(folder) for folder in folders)} tracks in {len(folders)} folders\n"
        )
        self.set_compilation_tags(folders)
        results = self.local.save_tracks_in_collections(collections=folders)

        if results:
            self.logger.print(STAT)
        self.local.library.log_save_tracks_result(results)
        log_prefix = "Would have set" if self.manager.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        self.logger.print()
        self.logger.debug("Update compilations: DONE")

    @dynamicprocessormethod
    def sync_remote(self) -> None:
        """Run all main functions for synchronising remote playlists with a local library"""
        self.logger.debug(f"Sync {self.remote.source}: START")

        self.local.load(types=LoadTypesLocal.playlists)
        self.remote.load(types=LoadTypesRemote.playlists)

        playlists = copy(list(self.local.library.playlists.values()))
        for pl in playlists:  # so filter_playlists doesn't clear the list of tracks on the original playlist objects
            pl._tracks = pl.tracks.copy()

        results = self.remote.sync(playlists)

        self.remote.library.log_sync(results)
        self.logger.debug(f"Sync {self.remote.source}: DONE")

    @dynamicprocessormethod
    def download(self) -> None:
        """Run the :py:class:`ItemDownloadHelper`"""
        self.logger.debug("Download helper: START")

        responses = self.remote.api.get_user_items(kind=RemoteObjectType.PLAYLIST, use_cache=self.remote.use_cache)
        playlists: Collection[RemotePlaylist] = self.manager.filter(list(map(
            lambda response: self.remote.factory.playlist(response, skip_checks=True), responses
        )))
        self.remote.api.get_items(playlists, kind=RemoteObjectType.PLAYLIST, use_cache=self.remote.use_cache)

        self.manager.run_download_helper(playlists)

        self.logger.debug("Download helper: DONE")

    @dynamicprocessormethod
    def new_music(self) -> None:
        """Create a new music playlist for followed artists with music released between ``start`` and ``end``"""
        self.logger.debug("New music playlist: START")

        name, results = self.manager.create_new_music_playlist()

        self.logger.print(STAT)
        self.remote.library.log_sync({name: results})
        log_prefix = "Would have added" if self.manager.dry_run else "Added"
        self.logger.info(f"\33[92m{log_prefix} {results.added} new tracks to playlist: '{name}' \33[0m")

        self.logger.debug("New music playlist: DONE")
