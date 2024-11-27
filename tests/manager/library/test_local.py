from pathlib import Path
from random import randrange

import pytest
from musify.libraries.local.library import LocalLibrary, MusicBee

from mocks.local import LocalLibraryMock, LocalTrackMock, MusicBeeMock
from musify_cli.config.library import PlaylistsConfig
from musify_cli.config.library.local import LocalLibraryConfig, LocalPaths, UpdaterConfig, MusicBeeConfig, MusicBeePaths
from musify_cli.config.library.types import LoadTypesLocal
from musify_cli.manager.library import LocalLibraryManager
from tests.manager.library.testers import LibraryManagerTester


class TestLocalLibraryManager[L: LocalLibrary, C: LocalLibraryConfig](LibraryManagerTester[LocalLibraryManager[L, C]]):

    library_mock: type[LocalLibraryMock] = LocalLibraryMock
    track_mock: type[LocalTrackMock] = LocalTrackMock

    @pytest.fixture
    def load_types(self) -> type[LoadTypesLocal]:
        return LoadTypesLocal

    @pytest.fixture
    def config(self, tmp_path: Path) -> C:
        library_folder = tmp_path.joinpath("library")
        library_folder.mkdir(parents=True, exist_ok=True)

        playlist_folder = tmp_path.joinpath("playlists")
        playlist_folder.mkdir(parents=True, exist_ok=True)

        return LocalLibraryConfig(
            name="name",
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
    def manager(self, config: C) -> LocalLibraryManager[L, C]:
        return LocalLibraryManager[L, C](config=config)

    @pytest.fixture
    def manager_mock(self, manager: LocalLibraryManager[L, C]) -> LocalLibraryManager[L, C]:
        """
        Replace the instantiated library from the given ``manager`` with a mocked library.
        Yields the modified ``manager`` as a pytest.fixture.
        """
        manager.config.__class__._library_cls = self.library_mock
        return manager

    def test_properties(self, manager: LocalLibraryManager[L, C]):
        assert manager.source == LocalLibrary.source

    ###########################################################################
    ## Operations
    ###########################################################################
    def test_merge_tracks(self, manager_mock: LocalLibraryManager[L, C], config: C):
        manager_mock.dry_run = False

        tracks = [self.track_mock() for _ in range(randrange(2, 5))]
        manager_mock.merge_tracks(tracks)

        library_mock: LocalLibraryMock = manager_mock.library
        assert library_mock.merge_tracks_args["tracks"] == tracks
        assert library_mock.merge_tracks_args["tags"] == config.updater.tags


class TestMusicBeeManager(TestLocalLibraryManager[MusicBee, MusicBeeConfig]):

    library_mock: type[MusicBeeMock] = MusicBeeMock

    @pytest.fixture
    def library_folders(self, tmp_path: Path) -> list[Path]:
        """The library folders to use when generating the MusicBee settings file."""
        library_folders = [tmp_path.joinpath("library_1"), tmp_path.joinpath("library_2")]
        for path in library_folders:
            path.mkdir(parents=True, exist_ok=True)
        return library_folders

    # noinspection PyMethodOverriding
    @pytest.fixture
    def config(self, tmp_path: Path, library_folders: list[Path]) -> MusicBeeConfig:
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

        return MusicBeeConfig(
            name="name",
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
    def manager(self, config: MusicBeeConfig):
        return LocalLibraryManager[MusicBee, MusicBeePaths](config=config)

    def test_properties(self, manager: MusicBeeConfig):
        assert manager.source == MusicBee.source
