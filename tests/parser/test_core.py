from datetime import datetime
from pathlib import Path
from random import choice

import pytest
from musify.field import TagFields
from musify.libraries.local.track.field import LocalTrackField
from musify.logger import MusifyLogger

from musify_cli import MODULE_ROOT
# noinspection PyProtectedMember
from musify_cli.parser.core import Paths, Logging, MUSIFY_ROOT, AIOREQUESTFUL_ROOT, MusifyConfig
# noinspection PyProtectedMember
from musify_cli.parser.library import LibrariesConfig, RemoteLibraryConfig, SpotifyAPIConfig, LocalLibraryConfig, \
    LocalPaths
from musify_cli.parser.types import LoadTypesLocal, LoadTypesRemote, EnrichTypesRemote
from tests.utils import path_resources

path_core_config = path_resources.joinpath("test_config.yml")


class TestLogging:
    @pytest.fixture
    def model(self) -> Logging:
        return Logging(
            name="test",
            compact=choice([True, False]),
            bars=choice([True, False]),
            formatters={
                "formatter1": {"format": "\\33[92mGreen text\\33[0m normal test: %(message)s"},
                "formatter2": {"format": "normal test \\33[91m Red text\\33[0m: %(message)s"},
            },
            loggers={
                "dev": {"level": "DEBUG"},
                "test": {"level": "INFO"},
                "prod": {"level": "WARNING"},
            }
        )

    def test_gets_logger(self, model: Logging):
        assert model.logger == model.loggers.get(model.name)
        model.name = "I am not a valid logger name"
        assert not model.logger

    def test_configures_additional_loggers(self, model: Logging):
        name = "i am an additional logger name"
        model.configure_additional_loggers(name)
        assert name in model.loggers
        assert model.loggers[name] == model.logger

        additional_logger_names = {MODULE_ROOT, MUSIFY_ROOT, AIOREQUESTFUL_ROOT}
        assert all(name in model.loggers and model.loggers[name] == model.logger for name in additional_logger_names)

    def test_ansi_codes_fixed(self, model: Logging):
        for formatter in model.formatters.values():
            assert "\\33" not in formatter["format"]

    def test_configure_logging(self, model: Logging):
        model.configure_logging()

        assert MusifyLogger.compact is model.compact
        assert MusifyLogger.disable_bars is not model.bars


class TestPaths:
    @pytest.fixture
    def model(self, tmp_path: Path) -> Paths:
        return Paths(
            base=tmp_path,
            backup=Path("path", "to", "backup"),
            cache="test_cache",
            token="test_token",
            local_library_exports=Path("path", "to", "local_library"),
        )

    def test_assigns_base_path_on_relative(self, model: Paths, tmp_path: Path):
        assert model.backup == tmp_path.joinpath("path", "to", "backup", model._dt_as_str)
        assert model.cache == tmp_path.joinpath("test_cache")
        assert model.token == tmp_path.joinpath("test_token")
        assert model.local_library_exports == tmp_path.joinpath("path", "to", "local_library")

    def test_keeps_path_on_absolute(self, tmp_path: Path):
        model = Paths(
            base=tmp_path.parent.parent,
            backup=tmp_path.joinpath("path", "to", "backup"),
            cache=tmp_path.joinpath("test_cache"),
            token=tmp_path.joinpath("test_token"),
            local_library_exports=tmp_path.joinpath("path", "to", "local_library"),
        )

        assert model.backup == tmp_path.joinpath("path", "to", "backup", model._dt_as_str)
        assert model.cache == tmp_path.joinpath("test_cache")
        assert model.token == tmp_path.joinpath("test_token")
        assert model.local_library_exports == tmp_path.joinpath("path", "to", "local_library")

    def test_removes_empty_directories(self, model: Paths):
        assert model._paths
        paths = list(model._paths.values()) + [model.base]
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)
            assert path.exists()

        model.remove_empty_directories()
        for path in paths:
            assert not path.exists()


class TestConfig:
    @pytest.fixture
    def model(self, tmp_path: Path):
        return MusifyConfig(
            libraries=LibrariesConfig(
                local=LocalLibraryConfig(
                    name="test",
                    type="local",
                    paths=LocalPaths(library=tmp_path)
                ),
                remote=RemoteLibraryConfig[SpotifyAPIConfig](
                    name="test",
                    type="spotify",
                    api=SpotifyAPIConfig(
                        client_id="",
                        client_secret="",
                        token_file_path="token.json"
                    )
                )
            )
        )

    def test_assigns_base_path_on_relative(self, model: MusifyConfig):
        path: Path = model.libraries.remote.api.token_file_path
        assert path.is_absolute()
        assert path.is_relative_to(model.paths.base)

    def test_keeps_path_on_absolute(self, model: MusifyConfig, tmp_path: Path):
        model = MusifyConfig(
            libraries=LibrariesConfig(
                local=model.libraries.local,
                remote=RemoteLibraryConfig[SpotifyAPIConfig](
                    name=model.libraries.remote.name,
                    api=SpotifyAPIConfig(
                        client_id=model.libraries.remote.api.client_id,
                        client_secret=model.libraries.remote.api.client_secret,
                        token_file_path=tmp_path.joinpath("token.json")
                    )
                )
            )
        )

        path: Path = model.libraries.remote.api.token_file_path
        assert path.is_absolute()
        assert not path.is_relative_to(model.paths.base)
        assert path == tmp_path.joinpath("token.json")

    # noinspection PyTestUnpassedFixture
    def test_load_from_file(self, tmp_path: Path):
        config, functions = MusifyConfig.from_file(path_core_config)

        assert config.execute

        assert config.paths.base == config.paths.model_fields.get("base").default
        assert config.paths.backup == config.paths.base.joinpath("test_backups", config.paths._dt_as_str)
        assert config.paths.cache == config.paths.base.joinpath("test_cache")
        assert config.paths.token == config.paths.base.joinpath("test_token")
        assert config.paths.local_library_exports == config.paths.base.joinpath("test_library_local")

        assert config.logging.name == "logger"
        assert config.logging.compact
        assert config.logging.bars
        assert config.logging.disable_existing_loggers

        values = ["include me", "exclude me", "and me"]
        assert config.pre_post.filter(values) == ["include me"]
        assert config.pre_post.pause == "this is a test message"

        assert config.pre_post.reload.local.types == [LoadTypesLocal.TRACKS]
        assert config.pre_post.reload.remote.types == [LoadTypesRemote.SAVED_TRACKS, LoadTypesRemote.SAVED_ALBUMS]
        assert config.pre_post.reload.remote.extend
        assert config.pre_post.reload.remote.enrich.enabled
        assert config.pre_post.reload.remote.enrich.types == [EnrichTypesRemote.TRACKS, EnrichTypesRemote.ALBUMS]

        assert config.libraries.local.name == "local"
        assert config.libraries.local.type == "local"

        assert config.libraries.remote.name == "spotify"
        assert config.libraries.remote.type == "Spotify"

        assert config.libraries.remote.download.urls == [
            "https://www.google.com/search?q={}",
            "https://www.youtube.com/results?search_query={}",
        ]
        assert config.libraries.remote.download.fields == (TagFields.ARTIST, TagFields.ALBUM)
        assert config.libraries.remote.download.interval == 1

        assert config.libraries.remote.new_music.name == "New Music - 2023"
        assert config.libraries.remote.new_music.start == datetime(2023, 1, 1).date()
        assert config.libraries.remote.new_music.end == datetime(2023, 12, 31).date()

        assert config.backup.key == "test key"

        assert config.reports.playlist_differences.enabled
        values = ["a", "b", "c", 1, 2, 3, "you", "and", "me"]
        assert config.reports.playlist_differences.filter(values) == ["a", "b", "c"]
        assert not config.reports.missing_tags.enabled
        assert not config.reports.missing_tags.filter.ready
        assert config.reports.missing_tags.tags == (
            LocalTrackField.TITLE,
            LocalTrackField.ARTIST,
            LocalTrackField.ALBUM,
            LocalTrackField.TRACK_NUMBER,
            LocalTrackField.TRACK_TOTAL,
        )
        assert config.reports.missing_tags.match_all


