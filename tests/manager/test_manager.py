import logging

import pytest
from jsonargparse import Namespace
from musify.log.logger import MusifyLogger

from musify_cli import MODULE_ROOT
from musify_cli.exception import ParserError
from musify_cli.manager import MusifyManager
# noinspection PyProtectedMember
from musify_cli.manager._core import ReportsManager
from musify_cli.parser import LOCAL_LIBRARY_TYPES, REMOTE_LIBRARY_TYPES
from tests.utils import path_txt, path_logging_config


class TestReportsManager:
    @pytest.fixture
    def config(self) -> Namespace:
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

    def test_playlist_differences(self, config: Namespace):
        manager = ReportsManager(config.reports, parent=MusifyManager(config))
        assert manager

    def test_missing_tags(self, config: Namespace):
        manager = ReportsManager(config.reports, parent=MusifyManager(config))
        assert manager


class TestMusifyManager:

    def test_all_libraries_supported(self):
        # noinspection PyProtectedMember
        assert set(MusifyManager._local_library_map) == set(LOCAL_LIBRARY_TYPES)
        # noinspection PyProtectedMember
        assert set(MusifyManager._remote_library_map) == set(REMOTE_LIBRARY_TYPES)

    @pytest.mark.skip(reason="this removes all handlers hence removing ability to see logs for tests that follow this")
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
