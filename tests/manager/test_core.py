import logging
from pathlib import Path

import pytest
from jsonargparse import Namespace
from musify.logger import MusifyLogger

from musify_cli import MODULE_ROOT
from musify_cli.exception import ParserError
from musify_cli.manager import MusifyManager
# noinspection PyProtectedMember
from musify_cli.manager._core import ReportsManager
from musify_cli.parser import LOCAL_LIBRARY_TYPES, REMOTE_LIBRARY_TYPES
# noinspection PyProtectedMember
from musify_cli.parser._utils import get_comparers_filter
from tests.utils import path_txt, path_logging_config


@pytest.mark.skip(reason="Tests not yet implemented")
class TestReportsManager:
    @pytest.fixture
    def config(self) -> Namespace:
        """
        Yields a valid :py:class:`Namespace` representing the config
        for the current manager as a pytest.fixture.
        """
        return Namespace(
            execute=False,
            libraries=Namespace(
                local=Namespace(
                    name="local",
                    type="local",
                ),
                remote=Namespace(
                    name="spotify",
                    type="spotify",
                ),
            ),
            reports=Namespace(

            )
        )

    @pytest.fixture
    def manager(self, config: Namespace) -> ReportsManager:
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
    def config(self, tmp_path: Path) -> Namespace:
        """
        Yields a valid :py:class:`Namespace` representing the config
        for the current manager as a pytest.fixture.
        """
        return Namespace(
            execute=True,
            paths=Namespace(
                base=tmp_path,
                backup=Path("path", "to", "backup"),
                token="test_token",
                cache="test_cache",
                local_library=Path("path", "to", "local_library"),
            ),
            backup=Namespace(key="KEY"),
            pause=None,
            filter=get_comparers_filter(["playlist 1", "playlist 2"]),
            reports=Namespace(),
            libraries=Namespace(
                local=Namespace(
                    name="local",
                    type="local",
                ),
                remote=Namespace(
                    name="remote",
                    type="spotify",
                ),
            )
        )

    @pytest.fixture
    def manager(self, config: Namespace) -> MusifyManager:
        """Yields a valid :py:class:`MusifyManager` for the current remote source as a pytest.fixture."""
        return MusifyManager(config=config)

    def test_all_libraries_supported(self):
        # noinspection PyProtectedMember
        assert set(MusifyManager._local_library_map) == set(LOCAL_LIBRARY_TYPES)
        # noinspection PyProtectedMember
        assert set(MusifyManager._remote_library_map) == set(REMOTE_LIBRARY_TYPES)

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_set_config(self, manager: MusifyManager):
        pass  # TODO

    def test_init_dry_run(self, manager: MusifyManager):
        dry_run = manager.dry_run
        assert dry_run is not manager.config.execute
        assert not manager._dry_run

        # does not generate a new object when called twice even if config changes
        manager.config.execute = not manager.config.execute
        assert manager.dry_run is manager.config.execute
        assert id(manager.dry_run) == id(manager._dry_run) == id(dry_run)

    def test_init_backup_key(self, manager: MusifyManager):
        assert manager.backup_key == manager.config.backup.key

        # always generates a new object when called twice
        manager.config.backup.key = "i am a new key"
        assert manager.backup_key == manager.config.backup.key

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
    def test_filter(self, manager: MusifyManager, config: Namespace):
        playlists = [f"playlist {i}" for i in range(1, 5)]
        assert manager.filter(playlists) == config.filter(playlists) == playlists[:2]

        # uses the new filter in the config
        config.filter = get_comparers_filter(["new playlist 1", "new playlist 2", "new playlist 3"])
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
