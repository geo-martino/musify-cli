import logging
from pathlib import Path

import pytest
from musify.logger import MusifyLogger

from musify_cli import MODULE_ROOT
from musify_cli.config.core import MusifyConfig, Reports, Paths, Backup, PrePost
from musify_cli.config.library import LibrariesConfig
from musify_cli.config.library.local import LocalLibraryConfig, LocalPaths
from musify_cli.config.library.remote import SpotifyLibraryConfig, SpotifyAPIConfig
from musify_cli.exception import ParserError
from musify_cli.manager import MusifyProcessor
from tests.utils import path_txt, path_logging_config


class TestMusifyProcessor:
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
    def manager(self, config: MusifyConfig) -> MusifyProcessor:
        """Yields a valid :py:class:`MusifyProcessor` for the current remote source as a pytest.fixture."""
        return MusifyProcessor(config=config)

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_set_config(self, manager: MusifyProcessor):
        pass  # TODO

    @pytest.mark.skip(reason="This removes all handlers hence removing ability to see logs for tests that follow this")
    def test_configure_logging(self):
        with pytest.raises(ParserError):
            MusifyProcessor.configure_logging(path_txt)

        MusifyProcessor.configure_logging(path_logging_config)
        assert MusifyLogger.compact

        loggers = [logger.name for logger in logging.getLogger().getChildren()]
        assert "__main__" not in loggers

        MusifyProcessor.configure_logging(path_logging_config, "test", "__main__")

        loggers = [logger.name for logger in logging.getLogger().getChildren()]
        assert "test" in loggers
        assert "__main__" in loggers
        assert MODULE_ROOT in loggers

    ###########################################################################
    ## Pre-/Post- operations
    ###########################################################################
    @pytest.mark.skip(reason="Test not yet implemented")
    def test_load(self, manager: MusifyProcessor):
        pass  # TODO

    ###########################################################################
    ## Utilities
    ###########################################################################
    def test_filter(self, manager: MusifyProcessor, config: MusifyConfig):
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
    def test_run_download_helper(self, manager: MusifyProcessor):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_create_new_music_playlist(self, manager: MusifyProcessor):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_playlist_differences(self, manager: MusifyProcessor):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_missing_tags(self, manager: MusifyProcessor):
        pass  # TODO
