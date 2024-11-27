from collections.abc import Collection
from pathlib import Path
from random import randrange
from typing import Any

import pytest
from musify.field import TagField, Fields
from musify.libraries.collection import BasicCollection
from musify.libraries.core.object import Track
from musify.libraries.local.library import LocalLibrary, MusicBee
from musify.libraries.local.track import LocalTrack, SyncResultTrack, FLAC
from musify.libraries.local.track.field import LocalTrackField, LocalTrackField as Tags
from musify.types import UnitIterable

from musify_cli.manager.library import LocalLibraryManager, MusicBeeManager
from musify_cli.config.library import PlaylistsConfig
from musify_cli.config.library.local import LocalLibraryConfig, LocalPaths, UpdaterConfig
from musify_cli.config.library.types import LoadTypesLocal
from tests.manager.library.testers import LibraryManagerTester
from tests.utils import random_str


class TestLocalLibraryManager[T: LocalLibraryManager](LibraryManagerTester[T]):

    @pytest.fixture
    def load_types(self) -> type[LoadTypesLocal]:
        return LoadTypesLocal

    @pytest.fixture
    def config(self, tmp_path: Path) -> LocalLibraryConfig:
        library_folder = tmp_path.joinpath("library")
        library_folder.mkdir(parents=True, exist_ok=True)

        playlist_folder = tmp_path.joinpath("playlists")
        playlist_folder.mkdir(parents=True, exist_ok=True)

        return LocalLibraryConfig(
            name="name",
            type=LocalLibrary.source,
            paths=LocalPaths(
                library=library_folder,
                playlists=playlist_folder,
                map={
                    "/different/folder": str(library_folder),
                    "/another/path": str(library_folder),
                }
            ),
            playlists=PlaylistsConfig(
                filter=["playlist 1", "playlist 2"],
            ),
            updater=UpdaterConfig(
                tags=["album", "album_artist", "track", "disc", "compilation"],
                replace=True
            )
        )

    @pytest.fixture
    def manager(self, config: LocalLibraryConfig) -> T:
        return LocalLibraryManager(config=config)

    @pytest.fixture
    def manager_mock(self, manager: T) -> T:
        """
        Replace the instantiated library from the given ``manager`` with a mocked library.
        Yields the modified ``manager`` as a pytest.fixture.
        """
        manager._library_cls = self.LibraryMock
        return manager

    def test_properties(self, manager: T):
        assert manager.source == LocalLibrary.source

    ###########################################################################
    ## Operations
    ###########################################################################
    class LibraryMock(LocalLibrary):

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

    class TrackMock(FLAC):

        # noinspection PyMissingConstructor
        def __init__(self):
            self.save_args: dict[str, Any] = {}
            self.merge_tracks_args: dict[str, Any] = {}

        def reset(self):
            """Reset all mock attributes"""
            self.save_args.clear()

        @property
        def path(self):
            return random_str()

        @property
        def album(self):
            return random_str()

        async def save(
                self,
                tags: UnitIterable[Tags] = Tags.ALL,
                replace: bool = False,
                dry_run: bool = True
        ) -> SyncResultTrack:
            self.save_args = {"tags": tags, "replace": replace, "dry_run": dry_run}
            return SyncResultTrack(saved=not dry_run, updated={tag: 0 for tag in tags})

    async def test_save_tracks(self, manager_mock: T, config: LocalLibraryConfig):
        manager_mock.dry_run = False

        await manager_mock.save_tracks()

        library_mock: TestLocalLibraryManager.LibraryMock = manager_mock.library
        assert library_mock.save_tracks_args["tags"] == config.updater.tags
        assert library_mock.save_tracks_args["replace"] == config.updater.replace
        assert library_mock.save_tracks_args["dry_run"] == manager_mock.dry_run

    # noinspection PyTestUnpassedFixture
    async def test_save_tracks_in_collections(self, manager_mock: T, config: LocalLibraryConfig):
        manager_mock.dry_run = False

        collections: list[BasicCollection[TestLocalLibraryManager.TrackMock]] = [
            BasicCollection(name=f"collection {i}", items=[self.TrackMock() for _ in range(randrange(2, 5))])
            for i in range(randrange(2, 5))
        ]
        await manager_mock.save_tracks_in_collections(collections)

        for coll in collections:
            for track in coll:
                assert track.save_args["tags"] == config.updater.tags
                assert track.save_args["replace"] == config.updater.replace
                assert track.save_args["dry_run"] == manager_mock.dry_run

    def test_merge_tracks(self, manager_mock: T, config: LocalLibraryConfig):
        manager_mock.dry_run = False

        tracks = [self.TrackMock() for _ in range(randrange(2, 5))]
        manager_mock.merge_tracks(tracks)

        library_mock: TestLocalLibraryManager.LibraryMock = manager_mock.library
        assert library_mock.merge_tracks_args["tracks"] == tracks
        assert library_mock.merge_tracks_args["tags"] == config.updater.tags


class TestMusicBeeManager(TestLocalLibraryManager[MusicBeeManager]):

    class LibraryMock(TestLocalLibraryManager.LibraryMock, MusicBee):
        pass

    @pytest.fixture
    def library_folders(self, tmp_path: Path) -> list[Path]:
        """The library folders to use when generating the MusicBee settings file."""
        library_folders = [tmp_path.joinpath("library_1"), tmp_path.joinpath("library_2")]
        for path in library_folders:
            path.mkdir(parents=True, exist_ok=True)
        return library_folders

    # noinspection PyMethodOverriding
    @pytest.fixture
    def config(self, tmp_path: Path, library_folders: list[Path]) -> LocalLibraryConfig:
        musicbee_folder = tmp_path.joinpath("library")
        musicbee_folder.mkdir(parents=True, exist_ok=True)

        playlists_folder = musicbee_folder.joinpath(MusicBee.playlists_path)
        playlists_folder.mkdir(parents=True, exist_ok=True)

        xml_library = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<!DOCTYPE plist PUBLIC \"-//Apple Computer//DTD PLIST 1.0//EN\" "
            "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">",
            "<plist version=\"1.0\">",
            "<dict>",
            "<key>Major Version</key><integer>3</integer>",
            "<key>Minor Version</key><integer>5</integer>",
            "<key>Application Version</key><string>3.5.8447.35892</string>",
            f"<key>Music Folder</key><string>file://localhost/{musicbee_folder}</string>",
            "<key>Library Persistent ID</key><string>3D76B2A6FD362901</string>",
            "<key>Tracks</key>",
            "<dict/>",
            "<key>Playlists</key>",
            "<array/>",
            "</dict>",
            "</plist>",
        )
        with open(musicbee_folder.joinpath(MusicBee.xml_library_path), "w") as f:
            f.write("\n".join(xml_library))

        xml_settings = (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>",
            "<ApplicationSettings xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
            "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\">",
            f"<Path>{musicbee_folder}</Path>",
            "<OrganisationMonitoredFolders>",
            f" <string>{library_folders[0]}</string>",
            f" <string>{library_folders[1]}</string>",
            "</OrganisationMonitoredFolders>",
            "</ApplicationSettings>",
        )
        with open(musicbee_folder.joinpath(MusicBee.xml_settings_path), "w") as f:
            f.write("\n".join(xml_settings))

        return LocalLibraryConfig(
            name="name",
            type=MusicBee.source,
            paths=LocalPaths(
                library=musicbee_folder,
                map={
                    "/different/folder": str(musicbee_folder),
                    "/another/path": str(musicbee_folder)
                }
            ),
            playlists=PlaylistsConfig(
                filter=["playlist 1", "playlist 2"],
            ),
            updater=UpdaterConfig(
                tags=["album", "album_artist", "track", "disc", "compilation"],
                replace=True
            )
        )

    @pytest.fixture
    def manager(self, config: LocalLibraryConfig) -> MusicBeeManager:
        return MusicBeeManager(config=config)

    def test_properties(self, manager: MusicBeeManager):
        assert manager.source == MusicBee.source
