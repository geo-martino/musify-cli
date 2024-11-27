import logging
from pathlib import Path

import pytest
from musify.logger import MusifyLogger

from musify_cli import MODULE_ROOT
from musify_cli.config.core import MusifyConfig, Reports, Paths, Backup, PrePost
from musify_cli.config.library import LibrariesConfig
from musify_cli.config.library.local import LOCAL_LIBRARY_CONFIG, LocalLibraryConfig, LocalPaths
from musify_cli.config.library.remote import REMOTE_LIBRARY_CONFIG, RemoteLibraryConfig, SpotifyAPIConfig, \
    SpotifyLibraryConfig
from musify_cli.exception import ParserError
from musify_cli.manager import MusifyManager
# noinspection PyProtectedMember
from musify_cli.manager._core import ReportsManager
from tests.utils import path_txt, path_logging_config


@pytest.mark.skip(reason="Tests not yet implemented")
class TestReportsManager:
    @pytest.fixture
    def config(self, tmp_path: Path) -> MusifyConfig:
        """
        Yields a valid :py:class:`Namespace` representing the config
        for the current manager as a pytest.fixture.
        """
        return MusifyConfig(
            execute=False,
            libraries=LibrariesConfig(
                local=LocalLibraryConfig(
                    name="local",
                    type="local",
                    paths=LocalPaths(library=tmp_path),
                ),
                remote=RemoteLibraryConfig(
                    name="spotify",
                    type="spotify",
                    api=SpotifyAPIConfig(client_id="", client_secret="")
                ),
            ),
            reports=Reports(

            )
        )

    @pytest.fixture
    def manager(self, config: MusifyConfig) -> ReportsManager:
        """Yields a valid :py:class:`MusifyManager` for the current remote source as a pytest.fixture."""
        return ReportsManager(config.reports, parent=MusifyManager(config))

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_playlist_differences(self, manager: ReportsManager):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_missing_tags(self, manager: ReportsManager):
        pass  # TODO


class TestMusifyManager:
    @pytest.fixture
    def config(self, tmp_path: Path) -> MusifyConfig:
        """
        Yields a valid :py:class:`Namespace` representing the config
        for the current manager as a pytest.fixture.
        """
        return MusifyConfig(
            execute=True,
            paths=Paths(
                base=tmp_path,
                backup=Path("path", "to", "backup"),
                token="test_token",
                cache="test_cache",
                local_library_exports=Path("path", "to", "local_library"),
            ),
            pre_post=PrePost(
                pause=None,
                filter=["playlist 1", "playlist 2"],
            ),
            backup=Backup(key="KEY"),
            reports=Reports(),
            libraries=LibrariesConfig(
                local=LocalLibraryConfig(
                    name="local",
                    paths=LocalPaths(library=tmp_path),
                ),
                remote=SpotifyLibraryConfig(
                    name="spotify",
                    api=SpotifyAPIConfig(client_id="<CLIENT ID>", client_secret="<CLIENT SECRET>")
                ),
            ),
        )

    @pytest.fixture
    def manager(self, config: MusifyConfig) -> MusifyManager:
        """Yields a valid :py:class:`MusifyManager` for the current remote source as a pytest.fixture."""
        return MusifyManager(config=config)

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_set_config(self, manager: MusifyManager):
        pass  # TODO

    @pytest.mark.skip(reason="This removes all handlers hence removing ability to see logs for tests that follow this")
    def test_configure_logging(self):
        with pytest.raises(ParserError):
            MusifyManager.configure_logging(path_txt)

        MusifyManager.configure_logging(path_logging_config)
        assert MusifyLogger.compact

        loggers = [logger.name for logger in logging.getLogger().getChildren()]
        assert "__main__" not in loggers

        MusifyManager.configure_logging(path_logging_config, "test", "__main__")

        loggers = [logger.name for logger in logging.getLogger().getChildren()]
        assert "test" in loggers
        assert "__main__" in loggers
        assert MODULE_ROOT in loggers

    ###########################################################################
    ## Pre-/Post- operations
    ###########################################################################
    @pytest.mark.skip(reason="Test not yet implemented")
    def test_load(self, manager: MusifyManager):
        pass  # TODO

    ###########################################################################
    ## Utilities
    ###########################################################################
    def test_filter(self, manager: MusifyManager, config: MusifyConfig):
        playlists = [f"playlist {i}" for i in range(1, 5)]
        assert manager.filter(playlists) == config.pre_post.filter(playlists) == playlists[:2]

        # uses the new filter in the config
        config.pre_post = PrePost(filter=["new playlist 1", "new playlist 2", "new playlist 3"])
        assert manager.filter(playlists) != playlists[:2]
        assert len(manager.filter([f"new {pl}" for pl in playlists])) == 3

    ###########################################################################
    ## Operations
    ###########################################################################
    @pytest.mark.skip(reason="Test not yet implemented")
    def test_run_download_helper(self, manager: MusifyManager):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_create_new_music_playlist(self, manager: MusifyManager):
        pass  # TODO
