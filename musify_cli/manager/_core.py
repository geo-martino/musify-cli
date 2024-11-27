from __future__ import annotations

import logging
import logging.config
from collections.abc import Collection, Iterable
from datetime import datetime
from functools import cached_property
from time import perf_counter
from typing import Self

from musify.base import MusifyItem
from musify.libraries.core.collection import MusifyCollection
from musify.libraries.remote.core.object import RemoteAlbum, SyncResultRemotePlaylist
from musify.libraries.remote.core.types import RemoteObjectType
from musify.logger import MusifyLogger, STAT
from musify.processors.download import ItemDownloadHelper
from musify.report import report_playlist_differences, report_missing_tags
from musify.types import UnitIterable
from musify.utils import to_collection

from musify_cli.exception import ParserError
from musify_cli.manager.library import LocalLibraryManager, MusicBeeManager
from musify_cli.manager.library import RemoteLibraryManager, SpotifyLibraryManager
from musify_cli.config.core import Reports, MusifyConfig
from musify_cli.config.library.local import LocalLibraryConfig
from musify_cli.config.library.types import LoadTypesLocal, LoadTypesRemote


class ReportsManager:
    """Configures options for running reports on Musify objects from a given ``config``."""
    def __init__(self, config: Reports, parent: MusifyManager):
        self.config = config
        self._parent: MusifyManager = parent

    def __await__(self):
        return self.run().__await__()

    async def run(self):
        """Run all configured reports for this manager,"""
        await self.playlist_differences()
        await self.missing_tags()

    async def playlist_differences(self) -> dict[str, dict[str, tuple[MusifyItem, ...]]]:
        """Generate a report on the differences between two library's playlists."""
        config = self.config.playlist_differences
        if not config.enabled:
            return {}

        await self._parent.local.load(types=[LoadTypesLocal.TRACKS, LoadTypesLocal.PLAYLISTS])
        await self._parent.remote.load(types=[LoadTypesRemote.PLAYLISTS])

        return report_playlist_differences(
            source=config.filter(self._parent.local.library.playlists.values()),
            reference=config.filter(self._parent.remote.library.playlists.values())
        )

    async def missing_tags(self) -> dict[str, dict[MusifyItem, tuple[str, ...]]]:
        """Generate a report on the items in albums from the local library that have missing tags."""
        config = self.config.missing_tags
        if not config.enabled:
            return {}

        await self._parent.local.load(types=LoadTypesLocal.TRACKS)

        source = config.filter(self._parent.local.library.albums)
        return report_missing_tags(collections=source, tags=config.tags, match_all=config.match_all)


class MusifyManager:
    """General class for managing various Musify objects, configured from a given ``config``."""

    _local_library_map: dict[str, type[LocalLibraryManager]] = {
        "local": LocalLibraryManager,
        "musicbee": MusicBeeManager,
    }

    _remote_library_map: dict[str, type[RemoteLibraryManager]] = {
        "spotify": SpotifyLibraryManager,
    }

    def __init__(self, config: MusifyConfig):
        start_time = perf_counter()

        # noinspection PyTypeChecker
        self.logger: MusifyLogger = logging.getLogger(__name__)

        self.config = config

        self.remote = self._create_remote_library_manager(self.config.libraries.remote)
        self.local = self._create_local_library_manager(self.config.libraries.local)
        self.reports: ReportsManager = ReportsManager(config=self.config.reports, parent=self)

        setup_time = perf_counter() - start_time
        self.logger.debug(f"{self.__class__.__name__} initialised. Time taken: {setup_time:.3f}")

    async def __aenter__(self) -> Self:
        await self.remote.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.config.paths.remove_empty_directories()
        await self.remote.__aexit__(exc_type, exc_val, exc_tb)

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
            self.remote.config = remote_library_config.get(remote_library_config.type)

        if (local_library_config := self.config.libraries.local).name != self.local.name:
            if self.local.initialised:
                raise ParserError(
                    "New local library given but the library manager has already been initialised | "
                    f"Current: {self.local.name!r} | New: {local_library_config.name!r}"
                )
            self.local = self._create_local_library_manager(local_library_config)
        else:
            self.local.config = local_library_config.get(local_library_config.type)

        self.reports.config = self.config.reports

    def _create_local_library_manager(self, config: LocalLibraryConfig) -> LocalLibraryManager:
        return self._local_library_map[config.type.casefold()](
            config=config, dry_run=self.dry_run, remote_wrangler=self.remote.wrangler
        )

    def _create_remote_library_manager(self, config: LocalLibraryConfig) -> RemoteLibraryManager:
        return self._remote_library_map[config.type.casefold()](
            config=config, dry_run=self.dry_run,
        )

    @property
    def execution_dt(self) -> datetime:
        """The timestamp of when the program was executed."""
        return self.config.paths.dt

    @cached_property
    def dry_run(self) -> bool:
        """Whether to run all write operations"""
        return not self.config.execute

    @property
    def backup_key(self) -> str | None:
        """The key to give to backups + the key to restore from"""
        return self.config.backup.key

    ###########################################################################
    ## Pre-/Post- operations
    ###########################################################################
    async def run_pre(self) -> None:
        """Run all pre-processor operations."""
        await self.load(True)

    async def run_post(self) -> None:
        """Run all post-processor operations."""
        self.pause()

    async def load(self, force: bool = False) -> None:
        """Reload the libraries according to the configured settings."""
        config_local = self.config.pre_post.reload.local
        if config_local.types:
            self.logger.debug("Load local library: START")
            await self.local.load(types=config_local.types or (), force=force)
            self.logger.debug("Load local library: DONE")

        config_remote = self.config.pre_post.reload.remote
        if any([config_remote.types, config_remote.extend, config_remote.enrich.enabled]):
            self.logger.debug("Load remote library: START")

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

            self.logger.debug("Load remote library: DONE")

    def pause(self) -> None:
        """Pause the application and display message if configured."""
        if pause := self.config.pre_post.pause:
            self.logger.print_line()
            input(f"\33[93m{pause}\33[0m ")

    ###########################################################################
    ## Utilities
    ###########################################################################
    def filter[T: Collection](self, items: T) -> T:
        """Run the generic filter on the given ``items`` if configured."""
        print(self.config.pre_post.filter)
        if (filter_ := self.config.pre_post.filter) is not None and filter_.ready:
            return filter_(items)
        return items

    def get_new_artist_albums(self) -> list[RemoteAlbum]:
        """Wrapper for :py:meth:`RemoteLibraryManager.filter_artist_albums_by_date`"""
        config = self.config.libraries.remote.new_music
        return self.remote.filter_artist_albums_by_date(start=config.start, end=config.end)

    async def extend_albums(self, albums: Iterable[RemoteAlbum]) -> None:
        """Extend responses of given ``albums`` to include all available tracks for each album."""
        kind = RemoteObjectType.ALBUM
        key = self.remote.api.collection_item_map[kind]

        await self.logger.get_asynchronous_iterator(
            (self.remote.api.extend_items(album.response, kind=kind, key=key, leave_bar=False) for album in albums),
            desc="Getting album tracks",
            unit="albums"
        )
        for album in albums:
            album.refresh(skip_checks=False)
