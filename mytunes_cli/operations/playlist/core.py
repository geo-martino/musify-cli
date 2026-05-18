import os
import shutil
from collections.abc import MutableSequence, Collection, Generator
from contextlib import contextmanager
from copy import copy
from pathlib import Path
from typing import Self

from mytunes.annotation import StrippedString
from mytunes.core.collection import SYNC_TYPE
from mytunes.core.properties.logger import HasProgress
from mytunes.core.sequence import UniqueSequence, MutableUniqueSequence
from mytunes.exception import MyTunesValidationError
from mytunes.local.library import LocalLibrary, MusicBee
from mytunes.local.playlist import LocalPlaylist, M3U
from pydantic import Field, model_validator

from mytunes_cli.operations._base import LocalToRemoteOperation, LocalLibraryOperation, \
    CrossLibraryOperation
from mytunes_cli.operations._filters import HasPlaylistFilter
from mytunes_cli.operations.report.playlist import PlaylistDifferenceReport


class ExportLocalPlaylists(LocalLibraryOperation, HasPlaylistFilter[LocalPlaylist], HasProgress):
    path: Path | None = Field(
        description=(
            "The directory to save the exported playlists to. If None, export to the library's playlist folder."
        ),
        default=Path("exports"),
        validation_alias="output",
    )
    clear: bool = Field(
        description="Whether to clear the exported playlists directory before exporting.",
        default=False,
    )

    @model_validator(mode="after")
    def _set_output_path(self) -> Self:
        if self.path is None:
            self.path = self.library.playlist_folder
        if self.path is None:
            raise MyTunesValidationError("Output path not set.")
        return self

    @property
    def output_dir(self) -> Path:
        path = self.path
        if not path.is_absolute():
            path = self.state.paths.application / path

        return path

    async def load(self) -> None:
        await self._load_playlists(self.library)

    async def run(self) -> None:
        playlists = self._get_playlists(self.library)
        self._log_start(playlists)

        async def _export_playlist(pl: LocalPlaylist) -> None:
            ext = next(iter(M3U.supported_extensions))
            path = pl.path.with_suffix("." + ext)

            if self.library.playlist_folder and path.is_relative_to(self.library.playlist_folder):
                path = path.relative_to(self.library.playlist_folder)
            else:
                path = path.name

            path = self.output_dir.joinpath(path)

            tracks = list(pl.tracks)
            if pl.sorter is not None:
                pl.sorter.sort(tracks)

            static = M3U(name=pl.name, path=path, path_mapper=pl.path_mapper)
            static.tracks.extend(tracks)
            await static.save(dry_run=self.state.dry_run)

        if self.clear and self.output_dir.is_dir():
            shutil.rmtree(self.output_dir)

        task_id = self._progress.add_task(description="Exporting playlists", total=len(playlists))
        await self._run_tasks_async(map(_export_playlist, playlists), task_id=task_id)

    def _log_start(self, playlists: list[LocalPlaylist]) -> None:
        message = (
            f"Exporting a static copy of {len(playlists)} {self.source} playlists to " +
            f"[bold blue]{self.output_dir}[/]"
        )
        self._logger.info(message, header=1, new_line_start=True)


class SyncLocalPlaylists(CrossLibraryOperation[LocalLibrary, LocalLibrary], HasPlaylistFilter[LocalPlaylist]):
    reference_name: StrippedString | None = Field(
        description="The name of the reference library, if applicable.",
        default=None,
        validation_alias="reference",
    )
    save: bool = Field(
        description="Whether to save the playlists back to the filesystem..",
        default=True,
    )

    @property
    def source(self) -> LocalLibrary:
        return self.state.get_local_library(self.source_name)

    @property
    def target(self) -> LocalLibrary:
        return self.state.get_local_library(self.target_name)

    @property
    def reference(self) -> LocalLibrary | None:
        return self.state.get_local_library(self.reference_name) if self.reference_name else None

    async def load(self) -> None:
        await self.source.load_tracks()
        await self.source.load_playlists()

        await self._load_library(self.target)

        if self.reference is None:
            return
        await self._load_library(self.reference)

    async def _load_library(self, library: LocalLibrary) -> None:
        if isinstance(library, MusicBee):
            await library.set_library_folders()

        if library.library_folders != self.source.library_folders:
            await library.load()
            return

        # operation is usually used to compare different sets of playlists for the same library
        # skip loading the same track multiple times if this is the case
        self.state.set_load_state(source=self.source.load_tracks, target=library.load_tracks)

        library.tracks.replace(self.source.tracks)
        await library.load_playlists()

    async def run(self) -> None:
        source_playlists = self._get_playlists(self.source)
        target_playlists = self._get_playlists(self.target)
        reference_playlists = self._get_playlists(self.reference) if self.reference is not None else []

        with self._normalise_playlist_paths(self.source, self.target, self.reference):
            await self._report_differences()

            self._log_start(source_playlists, target_playlists, reference_playlists)

            self._remove_playlists(source_playlists, target_playlists, reference_playlists)
            self._merge_playlists(source_playlists, target_playlists, reference_playlists)

            await self._report_differences()

        if self.save:
            await self._save_playlists()

    @staticmethod
    @contextmanager
    def _normalise_playlist_paths(*libraries: LocalLibrary | None) -> Generator[None]:
        original_paths: dict[Path, Path] = {}

        for library in libraries:
            if library is None:
                continue

            for playlist in library.playlists:
                absolute = playlist.path.absolute().with_suffix("")
                relative = absolute.relative_to(library.playlist_folder)

                original_paths[absolute] = playlist.path
                original_paths[relative] = playlist.path

                playlist.path = relative

            library.playlists.refresh()  # unique keys have changed

        yield

        for library in libraries:
            if library is None:
                continue

            for playlist in library.playlists:
                absolute = library.playlist_folder.joinpath(playlist.path)
                relative = playlist.path

                playlist.path = original_paths.get(absolute, library.playlist_folder.joinpath(original_paths[relative]))
                # ensure appropriate path mapper is set to any new playlists
                playlist.path_mapper = library.path_mapper

            library.playlists.refresh()  # unique keys have changed

    def _remove_playlists(
            self,
            source: MutableSequence[LocalPlaylist],
            target: MutableSequence[LocalPlaylist],
            reference: MutableSequence[LocalPlaylist] | None,
    ) -> None:
        if not reference:
            return

        # use unique sequences to compare playlists on their unique keys
        deleted = MutableUniqueSequence()
        deleted.extend(UniqueSequence(source).outer_difference(reference))  # get deleted from source
        deleted.extend(UniqueSequence(target).outer_difference(reference))  # get deleted from target
        deleted_paths = {pl.path for pl in deleted}

        for path in deleted_paths:
            self._remove_playlist(self.source, source, path)
            self._remove_playlist(self.target, target, path)
            self._remove_playlist(self.reference, reference, path)

    def _remove_playlist(self, library: LocalLibrary, playlists: MutableSequence[LocalPlaylist], path: Path) -> None:
        playlist = next((pl for pl in playlists if pl.path == path), None)
        if playlist is None:
            return

        library.playlists.remove(playlist)
        playlists.remove(playlist)

        path = library.playlist_folder.joinpath(playlist.path)
        if not self.state.dry_run and path.is_file():
            os.remove(path)

    def _merge_playlists(
            self,
            source: MutableSequence[LocalPlaylist],
            target: MutableSequence[LocalPlaylist],
            reference: MutableSequence[LocalPlaylist] | None,
    ) -> None:
        self.target.merge_playlists(source, reference=reference)
        self.source.merge_playlists(target, reference=reference)

        if self.reference is None:
            return

        self.reference.playlists.replace(map(copy, source))

    async def _save_playlists(self):
        await self.source.save_playlists(dry_run=self.state.dry_run)
        await self.target.save_playlists(dry_run=self.state.dry_run)

        if self.reference is None:
            return

        if not self.state.dry_run and self.reference.playlist_folder.is_dir():
            # clear all previous reference playlists
            shutil.rmtree(self.reference.playlist_folder)

        await self.reference.save_playlists(dry_run=self.state.dry_run)

    def _log_start(self, source: Collection, target: Collection, reference: Collection) -> None:
        message = (
            f"Synchronising {len(source)} playlists with {len(target)} playlists "
            f"from [bold blue]{self.target.playlist_folder}[/]"
        )
        if self.reference is not None:
            message += (
                f" [bold white]against {len(reference)} reference playlists from[/] "
                f"[bold blue]{self.reference.playlist_folder}[/]"
            )

        self._logger.info(message, header=1, new_line_start=True)

    async def _report_differences(self):
        report = PlaylistDifferenceReport(
            state=self.state,
            source_name=self.source_name,
            target_name=self.target_name,
            filter=self.filter,
        )
        await report.cli_cmd()

class SyncLocalAndRemotePlaylists(LocalToRemoteOperation, HasPlaylistFilter[LocalPlaylist]):
    type: SYNC_TYPE = Field(
        description=(
            "Sync option for the remote service.\n"
            "`new`: Do not clear any items from the remote service and only add new items.\n"
            "`refresh`: Clear all items from the remote service first, then add all items.\n"
            "`sync`: Clear all items not currently on the remote service, then add all items "
            "from this library not currently in the remote service.\n"
        ),
        default="sync",
    )

    async def load(self) -> None:
        await self._load_playlists(self.source)
        await self._load_playlists(self.target)

    async def run(self) -> None:
        playlists = self._get_playlists(self.source)
        self._log_start(playlists)

        self.target.merge_playlists(playlists)
        results = await self.target.sync_playlists(kind=self.type, dry_run=self.state.dry_run)

        self.target.log_sync_results(results)

    def _log_start(self, playlists: list[LocalPlaylist]) -> None:
        message = (
            f"Synchronising {len(playlists)} playlists with "
            f"{self.target.user.name}'s {self.target.source} library"
        )
        self._logger.info(message, header=1, new_line_start=True)
