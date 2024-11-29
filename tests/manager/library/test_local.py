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
    ## Backup/Restore
    ###########################################################################
    @pytest.mark.skip(reason="Test not yet implemented")
    def test_restore_library(self, manager_mock: LocalLibraryManager[L, C]):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_get_tags_to_restore_from_user(self, manager_mock: LocalLibraryManager[L, C]):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_get_tags_to_restore_from_user(self, manager_mock: LocalLibraryManager[L, C]):
        pass  # TODO

    ###########################################################################
    ## Operations
    ###########################################################################
    @pytest.mark.skip(reason="Test not yet implemented")
    def test_save_tracks(self, manager_mock: LocalLibraryManager[L, C], config: C):
        pass  # TODO

    def test_merge_tracks(self, manager_mock: LocalLibraryManager[L, C], config: C):
        manager_mock.dry_run = False

        tracks = [self.track_mock() for _ in range(randrange(2, 5))]
        manager_mock.merge_tracks(tracks)

        library_mock: LocalLibraryMock = manager_mock.library
        assert library_mock.merge_tracks_args["tracks"] == tracks
        assert library_mock.merge_tracks_args["tags"] == config.updater.tags

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_set_tags(self, manager_mock: LocalLibraryManager[L, C]):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_merge_playlists(self, manager_mock: LocalLibraryManager[L, C]):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_export_playlists(self, manager_mock: LocalLibraryManager[L, C]):
        pass  # TODO

class TestMusicBeeManager(TestLocalLibraryManager[MusicBee, MusicBeeConfig]):

    library_mock: type[MusicBeeMock] = MusicBeeMock

    # noinspection PyMethodOverriding
    @pytest.fixture
    def config(self, musicbee_folder: Path) -> MusicBeeConfig:
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
