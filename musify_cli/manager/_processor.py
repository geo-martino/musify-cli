from __future__ import annotations

import logging
import logging.config
import sys
from collections.abc import Collection, Callable
from datetime import datetime
from functools import cached_property
from time import perf_counter
from typing import Self, AsyncContextManager, Any

from musify.base import MusifyItem
from musify.libraries.local.track.field import LocalTrackField
from musify.logger import MusifyLogger, STAT
from musify.processors.base import dynamicprocessormethod, DynamicProcessor
from musify.report import report_playlist_differences, report_missing_tags

from musify_cli.config.core import MusifyConfig, Paths
from musify_cli.config.library.local import LocalLibraryConfig
from musify_cli.config.library.types import LoadTypesLocal, LoadTypesRemote
from musify_cli.exception import ParserError
from musify_cli.manager.library import LocalLibraryManager
from musify_cli.manager.library import RemoteLibraryManager


class MusifyProcessor(DynamicProcessor, AsyncContextManager):
    """
    General class for managing various Musify objects, configured from a given ``config``.
    Runs core functionality and meta-functions for the program.
    """

    @property
    def time_taken(self) -> float:
        """The total time taken since initialisation"""
        return perf_counter() - self._start_time

    @property
    def execution_dt(self) -> datetime:
        """The timestamp of when the program was executed."""
        return self.config.paths.dt

    @cached_property
    def dry_run(self) -> bool:
        """Whether to run all write operations"""
        return not self.config.execute

    @property
    def paths(self) -> Paths:
        """The configuration for this execution's paths"""
        return self.config.paths

    def __init__(self, config: MusifyConfig):
        super().__init__()
        self._start_time = perf_counter()

        # noinspection PyTypeChecker
        self.logger: MusifyLogger = logging.getLogger(__name__)
        sys.excepthook = self._handle_exception

        self.config = config
        self._dump_config("Base")

        self.remote = self._create_remote_library_manager(self.config.libraries.remote)
        self.local = self._create_local_library_manager(self.config.libraries.local)

        self.logger.debug(f"{self.__class__.__name__} initialised. Time taken: {self.time_taken:.3f}")

    def __await__(self):
        return self.run().__await__()

    async def __aenter__(self) -> Self:
        await self.remote.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.config.paths.remove_empty_directories()
        await self.remote.__aexit__(exc_type, exc_val, exc_tb)

    async def run(self) -> Any:
        """Run the processor and any pre-/post-operations around it."""
        self.logger.debug(f"Called processor '{self._processor_name}': START")
        await super().__call__()
        self.logger.debug(f"Called processor '{self._processor_name}': DONE\n")

    def set_processor(self, name: str, config: MusifyConfig = None) -> Callable[[], None]:
        """Set the processor to use from the given name"""
        self._set_processor_name(name)

        if config is not None:
            self.set_config(config)
            self._dump_config(name)

        return self._processor_method

    def set_config(self, config: MusifyConfig) -> None:
        """Set a new config for this manager and all composite managers"""
        self.config = config

        if (remote_library_config := self.config.libraries.remote).name != self.remote.name:
            if self.remote.initialised:
                raise ParserError(
                    "New remote library given but the library manager has already been initialised | "
                    f"Current: {self.remote.name!r} | New: {remote_library_config.name!r}"
                )
            self.remote = self._create_remote_library_manager(remote_library_config)
        else:
            self.remote.config = remote_library_config

        if (local_library_config := self.config.libraries.local).name != self.local.name:
            if self.local.initialised:
                raise ParserError(
                    "New local library given but the library manager has already been initialised | "
                    f"Current: {self.local.name!r} | New: {local_library_config.name!r}"
                )
            self.local = self._create_local_library_manager(local_library_config)
        else:
            self.local.config = local_library_config

    def _create_remote_library_manager(self, config: LocalLibraryConfig) -> RemoteLibraryManager:
        return RemoteLibraryManager(config=config, dry_run=self.dry_run)

    def _create_local_library_manager(self, config: LocalLibraryConfig) -> LocalLibraryManager:
        return LocalLibraryManager(config=config, dry_run=self.dry_run, remote_wrangler=self.remote.wrangler)

    def _dump_config(self, name: str = None) -> None:
        self.logger.debug(f"{self.get_func_log_name(name)} config:\n" + self.config.model_dump_yaml())

    def _handle_exception(self, exc_type, exc_value, exc_traceback) -> None:
        """Custom exception handler. Handles exceptions through logger."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        self.logger.critical(
            "CRITICAL ERROR: Uncaught Exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    def get_func_log_name(self, name: str = None) -> str:
        """Formats the given ``name`` to be appropriate for logging"""
        if not name:
            name = self._processor_name

        return name.replace("_", " ").replace("-", " ").title()

    def as_dict(self) -> dict[str, Any]:
        return {}

    ###########################################################################
    ## Utilities
    ###########################################################################
    def filter[T: Collection](self, items: T) -> T:
        """Run the generic filter on the given ``items`` if configured."""
        if (filter_ := self.config.pre_post.filter) is not None and filter_.ready:
            return filter_(items)
        return items

    ###########################################################################
    ## Backup/Restore
    ###########################################################################
    @dynamicprocessormethod
    async def backup_local(self) -> None:
        """Backup data for the local library"""
        await self.local.backup(self.paths.backup, key=self.config.backup.key)

    @dynamicprocessormethod
    async def backup_remote(self) -> None:
        """Backup data for the local library"""
        await self.remote.backup(self.paths.backup, key=self.config.backup.key)

    @dynamicprocessormethod
    async def restore_local(self) -> None:
        """Restore local library data from a backup, getting user input for the settings"""
        await self.local.restore(self.paths.backup.parent)

    @dynamicprocessormethod
    async def restore_remote(self) -> None:
        """Restore remote library data from a backup, getting user input for the settings"""
        await self.remote.restore(self.paths.backup.parent)

    ###########################################################################
    ## Pre-/Post- operations
    ###########################################################################
    async def run_pre(self) -> None:
        """Run all pre-processor operations."""
        await self.load(True)

    async def run_post(self) -> None:
        """Run all post-processor operations."""
        self.pause()

    def pause(self) -> None:
        """Pause the application and display message if configured."""
        if pause := self.config.pre_post.pause:
            self.logger.print_line()
            input(f"\33[93m{pause}\33[0m ")

    async def load(self, force: bool = False) -> None:
        """Load/reload the libraries according to the configured settings."""
        config_local = self.config.pre_post.reload.local
        if config_local.types:
            self.logger.debug(f"Load {self.local.source} library: START")
            await self.local.load(types=config_local.types or (), force=force)
            self.logger.debug(f"Load {self.local.source} library: DONE")

        config_remote = self.config.pre_post.reload.remote
        if any([config_remote.types, config_remote.extend, config_remote.enrich.enabled]):
            self.logger.debug(f"Load {self.remote.source} library: START")

            await self.remote.load(types=config_remote.types or (), force=force)
            if config_remote.extend:
                await self.remote.library.extend(self.local.library, allow_duplicates=False)
                self.logger.print_line(STAT)
            if config_remote.enrich.enabled:
                await self.remote.enrich(
                    types=config_remote.types or (),
                    enrich=config_remote.enrich.types or (),
                    force=force
                )

            self.logger.debug(f"Load {self.remote.source} library: DONE")

    ###########################################################################
    ## Cross-library operations
    ###########################################################################
    @dynamicprocessormethod
    async def search(self) -> None:
        """Run all methods for searching, checking, and saving URI associations for local files."""
        self.logger.debug("Search and match: START")

        await self.local.load(types=LoadTypesLocal.TRACKS)

        albums = self.local.library.albums
        [album.items.remove(track) for album in albums for track in album.items.copy() if track.has_uri is not None]
        albums = [album for album in albums if len(album.items) > 0]

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
        results = await self.local.save_tracks(collections=albums)

        if results:
            self.logger.print_line(STAT)
        self.local.library.log_save_tracks_result(results)
        log_prefix = "Would have set" if self.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        self.logger.debug("Search and match: DONE")

    @dynamicprocessormethod
    async def check(self) -> None:
        """Run check on entire library by album and update URI tags on file"""
        self.logger.debug("Check and update URIs: START")

        await self.local.load(types=LoadTypesLocal.TRACKS)

        folders = self.filter(self.local.library.folders)
        if not await self.remote.check(folders):
            self.logger.debug("Check and update URIs: DONE")
            return

        self.logger.info(f"\33[1;95m ->\33[1;97m Updating tags for {len(self.local.library)} tracks: uri \33[0m")
        results = await self.local.library.save_tracks(tags=LocalTrackField.URI, replace=True, dry_run=self.dry_run)

        if results:
            self.logger.print_line(STAT)
        self.local.library.log_save_tracks_result(results)
        self.logger.info(f"\33[92mSet tags for {len(results)} tracks \33[0m")

        self.logger.debug("Check and update URIs: DONE")

    @dynamicprocessormethod
    async def pull_tags(self) -> None:
        """Run all methods for pulling tag data from remote and updating local track tags"""
        self.logger.debug("Update tags: START")

        await self.local.load(types=LoadTypesLocal.TRACKS)
        await self.remote.library.extend(self.local.library, allow_duplicates=False)
        await self.remote.library.enrich_tracks(features=True, albums=True, artists=True)

        self.local.merge_tracks(self.remote.library)
        results = await self.local.save_tracks()

        if results:
            self.logger.print_line(STAT)
        self.local.library.log_save_tracks_result(results)
        log_prefix = "Would have set" if self.dry_run else "Set"
        self.logger.info(f"\33[92m{log_prefix} tags for {len(results)} tracks \33[0m")

        self.logger.debug("Update tags: DONE")

    @dynamicprocessormethod
    async def sync_remote(self) -> None:
        """Run all main functions for synchronising remote playlists with a local library"""
        self.logger.debug(f"Sync {self.remote.source}: START")

        await self.local.load()
        await self.remote.load(types=LoadTypesRemote.PLAYLISTS)

        results = await self.remote.config.playlists.sync.run(
            library=self.remote.library,
            playlists=self.local.library.playlists.values(),
            dry_run=self.dry_run,
        )

        self.remote.library.log_sync(results)
        self.logger.debug(f"Sync {self.remote.source}: DONE")

    ###########################################################################
    ## Local library operations
    ###########################################################################
    @dynamicprocessormethod
    async def auto_tag(self) -> None:
        """Run all methods for setting and saving tags according to user-defined rules."""
        await self.local.set_tags()

    @dynamicprocessormethod
    async def merge_playlists(self) -> None:
        """Merge playlists from a given folder with the currently loaded set of local playlists."""
        await self.local.merge_playlists(playlist_filter=self.config.pre_post.filter)

    @dynamicprocessormethod
    async def export_playlists(self) -> None:
        """Export a static copy of all local library playlists as M3U files."""
        await self.local.export_playlists(
            output_folder=self.paths.local_library_exports,
            playlist_filter=self.config.pre_post.filter,
        )

    ###########################################################################
    ## Remote library operations
    ###########################################################################
    @dynamicprocessormethod
    async def print(self) -> None:
        """Pretty print data from API getting input from user"""
        await self.remote.print()

    @dynamicprocessormethod
    async def download(self) -> None:
        """Run the :py:class:`ItemDownloadHelper`"""
        await self.remote.run_download_helper(self.filter)

    @dynamicprocessormethod
    async def new_music(self) -> None:
        """Create a playlist of new music released by user's followed artists"""
        await self.remote.create_new_music_playlist()

    ###########################################################################
    ## Reports
    ###########################################################################
    @dynamicprocessormethod
    async def report(self) -> None:
        """Produce various reports on loaded data"""
        self.logger.debug("Generate reports: START")
        await self._report_playlist_differences()
        await self._report_missing_tags()
        self.logger.debug("Generate reports: DONE")

    async def _report_playlist_differences(self) -> dict[str, dict[str, tuple[MusifyItem, ...]]]:
        """Generate a report on the differences between two library's playlists."""
        config = self.config.reports.playlist_differences
        if not config.enabled:
            return {}

        await self.local.load(types=[LoadTypesLocal.TRACKS, LoadTypesLocal.PLAYLISTS])
        await self.remote.load(types=[LoadTypesRemote.PLAYLISTS])

        source = config.filter(self.local.library.playlists.values()),
        reference = config.filter(self.remote.library.playlists.values())
        return report_playlist_differences(source=source, reference=reference)

    async def _report_missing_tags(self) -> dict[str, dict[MusifyItem, tuple[str, ...]]]:
        """Generate a report on the items in albums from the local library that have missing tags."""
        config = self.config.reports.missing_tags
        if not config.enabled:
            return {}

        await self.local.load(types=LoadTypesLocal.TRACKS)

        source = config.filter(self.local.library.albums)
        return report_missing_tags(collections=source, tags=config.tags, match_all=config.match_all)
