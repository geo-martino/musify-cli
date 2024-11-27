from collections.abc import Collection
from typing import Any

from musify.field import TagField, Fields
from musify.libraries.core.object import Track
from musify.libraries.local.library import LocalLibrary, MusicBee
from musify.libraries.local.track import LocalTrack, SyncResultTrack, FLAC
from musify.libraries.local.track.field import LocalTrackField, LocalTrackField as Tags
from musify.types import UnitIterable

from mocks.core import LibraryMock
from musify_cli.config.library.types import LoadTypesLocal
from tests.utils import random_str


class LocalTrackMock(FLAC):

    # noinspection PyMissingConstructor
    def __init__(self, *args, **kwargs):
        self.save_args: dict[str, Any] = {}
        self.merge_tracks_args: dict[str, Any] = {}

    def reset(self):
        """Reset all mock attributes"""
        self.save_args.clear()

    async def save(
            self,
            tags: UnitIterable[Tags] = Tags.ALL,
            replace: bool = False,
            dry_run: bool = True
    ) -> SyncResultTrack:
        self.save_args = {"tags": tags, "replace": replace, "dry_run": dry_run}
        return SyncResultTrack(saved=not dry_run, updated={tag: 0 for tag in tags})


class LocalLibraryMock(LibraryMock, LocalLibrary):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.load_calls: list[str] = []
        self.save_tracks_args: dict[str, Any] = {}
        self.merge_tracks_args: dict[str, Any] = {}

    def reset(self):
        """Reset all mock attributes"""
        self.load_calls.clear()
        self.save_tracks_args.clear()
        self.merge_tracks_args.clear()

    async def load(self):
        self.load_calls.append("ALL")

    async def load_tracks(self):
        self.load_calls.append(LoadTypesLocal.TRACKS.name)

    async def load_playlists(self):
        self.load_calls.append(LoadTypesLocal.PLAYLISTS.name)

    async def save_tracks(
            self,
            tags: UnitIterable[LocalTrackField] = LocalTrackField.ALL,
            replace: bool = False,
            dry_run: bool = True
    ) -> dict[LocalTrack, SyncResultTrack]:
        self.save_tracks_args = {"tags": tags, "replace": replace, "dry_run": dry_run}
        return {}

    def merge_tracks(self, tracks: Collection[Track], tags: UnitIterable[TagField] = Fields.ALL) -> None:
        self.merge_tracks_args = {"tracks": tracks, "tags": tags}


class MusicBeeMock(LocalLibraryMock, MusicBee):
    pass
