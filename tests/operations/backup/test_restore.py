from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock, Mock

import pytest
import yaml
from faker import Faker
from mytunes.core.library import Library
from mytunes.core.track import RemoteTrack
from mytunes.local.track import LocalTrack
from pydantic import ValidationError
from pytest_mock import MockerFixture

from mytunes_cli.log import DT_FORMAT
from mytunes_cli.operations.backup.restore import _BaseRestore, RestoreLocalLibrary, RestoreRemoteLibrary
from mytunes_cli.state import GlobalState
from tests.operations.testers import OperationTester
from tests.utils import patch_input


class TestBaseRestore(OperationTester):
    # noinspection PyAbstractClass
    @pytest.fixture
    @patch.multiple(
        _BaseRestore,
        __abstractmethods__=set(),
        _restore_library=MagicMock(),
    )
    def model(self, state: GlobalState, library_name: str, faker: Faker, tmp_path: Path) -> _BaseRestore:
        path = tmp_path / faker.word() / library_name
        path.mkdir(parents=True, exist_ok=True)
        return _BaseRestore(state=state, library_name=library_name, path=path)

    @pytest.fixture
    def valid_timestamps(self, model: _BaseRestore, faker: Faker) -> list[datetime]:
        timestamps = [faker.date_time().replace(microsecond=0) for _ in range(faker.random_int(1, 30))]

        for timestamp in timestamps:
            filename = f"{timestamp.strftime(DT_FORMAT)}.{faker.file_extension(category="text")}"
            path = model.backup_dir / filename

            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

        return timestamps

    @pytest.fixture
    def valid_timestamps_with_key(self, model: _BaseRestore, faker: Faker) -> list[datetime]:
        model.key = faker.word()

        timestamps = [faker.date_time().replace(microsecond=0) for _ in range(faker.random_int(1, 30))]

        for timestamp in timestamps:
            filename = f"{timestamp.strftime(DT_FORMAT)} ({model.key}).{faker.file_extension(category="text")}"
            path = model.backup_dir / filename

            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

        return timestamps

    @pytest.fixture
    def invalid_filenames(self, model: _BaseRestore, faker: Faker) -> list[str]:
        filenames = [faker.word() for _ in range(faker.random_int(1, 30))]

        for filename in filenames:
            filename += f".{faker.file_extension(category="text")}"
            path = model.backup_dir / filename

            path.mkdir(parents=True, exist_ok=True)
            path.touch()

        return filenames

    def test_paths(self, model: _BaseRestore, valid_timestamps: list[datetime], faker: Faker):
        timestamp = faker.random_element(valid_timestamps)
        model.backup_dir.mkdir(parents=True, exist_ok=True)
        model.backup_dir.joinpath(timestamp.strftime(DT_FORMAT)).with_suffix(".txt").touch()

        model.timestamp = timestamp
        assert model.backup_dir.name == model.library_name
        assert model.backup_path.name == model.backup_filename

    def test_filename(self, model: _BaseRestore, valid_timestamps: list[datetime], faker: Faker):
        model.timestamp = faker.random_element(valid_timestamps)

        model.key = None
        assert model.backup_filename == model.timestamp.strftime(DT_FORMAT)
        assert model.backup_path.name == model.backup_filename

        model.key = faker.word()
        assert model.backup_filename.startswith(model.timestamp.strftime(DT_FORMAT))
        assert model.key in model.backup_filename
        assert model.backup_path.name == model.backup_filename

    def test_validates_against_available_timestamps(
            self, model: _BaseRestore, valid_timestamps: list[datetime], invalid_filenames: list[str], faker: Faker
    ):
        assert sorted(model.backup_timestamps) == sorted(valid_timestamps)

        timestamp = faker.random_element(valid_timestamps)
        model.timestamp = timestamp
        assert model.timestamp == timestamp

        with pytest.raises(ValidationError, match="does not exist"):
            model.timestamp = min(valid_timestamps) - timedelta(seconds=1)

    def test_validates_against_available_timestamps_with_key(
            self,
            model: _BaseRestore,
            valid_timestamps: list[datetime],
            valid_timestamps_with_key: list[datetime],
            invalid_filenames: list[str],
            faker: Faker
    ):
        assert sorted(model.backup_timestamps) == sorted(valid_timestamps_with_key)

        timestamp = faker.random_element(valid_timestamps_with_key)
        model.timestamp = timestamp
        assert model.timestamp == timestamp

        invalid_timestamp = None
        while invalid_timestamp is None or invalid_timestamp in valid_timestamps_with_key:
            invalid_timestamp = min(valid_timestamps) - timedelta(seconds=1)

        with pytest.raises(ValidationError, match="does not exist"):
            model.timestamp = invalid_timestamp

    def test_set_timestamp_from_timestamp(self, model: _BaseRestore, valid_timestamps: list[datetime], faker: Faker):
        timestamp = faker.random_element(valid_timestamps)

        # adding some random input to check it skips unknown inputs
        with patch_input([*faker.words(), timestamp.strftime(DT_FORMAT)]):
            model.timestamp = None  # sets to default, triggering set name process

        assert model.timestamp == timestamp

    def test_set_timestamp_from_index(self, model: _BaseRestore, valid_timestamps: list[datetime], faker: Faker):
        timestamp = faker.random_element(valid_timestamps)

        # adding some random input to check it skips unknown inputs
        with patch_input([*faker.words(), sorted(valid_timestamps).index(timestamp) + 1]):
            model.timestamp = None  # sets to default, triggering set name process

        assert model.timestamp == timestamp

    async def test_load_yaml(self, model: _BaseRestore, valid_timestamps: list[datetime], library: Library, faker: Faker):
        model.timestamp = faker.random_element(valid_timestamps)
        dump = library.dump()
        file_path = Path(str(model.backup_path) + ".yaml")

        with file_path.open("w", encoding="utf-8") as file:
            yaml.dump(dump, file)

        result = await model._load_yaml()
        assert result == dump

    async def test_run_skips(self, model: _BaseRestore, invalid_filenames: list[str], faker: Faker):
        assert sorted(model.backup_timestamps) == []  # no available backups

        timestamp = faker.date_time()
        model.timestamp = timestamp
        assert model.timestamp != timestamp  # doesn't accept given timestamp when no backups available

        with patch.object(model, "_restore_library") as mock_restore_library:
            await model.run()  # doesn't do anything
            mock_restore_library.assert_not_called()

    async def test_run(self, model: _BaseRestore, valid_timestamps: list[datetime], faker: Faker):
        model.timestamp = faker.random_element(valid_timestamps)

        with patch.object(model, "_restore_library") as mock_restore_library:
            await model.run()
            mock_restore_library.assert_called_once()


class RestoreTester(OperationTester, metaclass=ABCMeta):
    @pytest.fixture
    def backup_name(self, model: _BaseRestore, faker: Faker) -> str:
        timestamp = faker.date_time().replace(microsecond=0)
        filename = f"{timestamp.strftime(DT_FORMAT)}.{faker.file_extension(category="text")}"
        path = model.backup_dir / filename

        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

        model.timestamp = timestamp
        return filename

    @abstractmethod
    def backup_dump(self, model: _BaseRestore, faker: Faker) -> dict[str, Any]:
        raise NotImplementedError


class TestRestoreLocalLibrary(RestoreTester):
    @pytest.fixture
    def model(self, state: GlobalState, local_library_name: str, faker: Faker, tmp_path: Path) -> RestoreLocalLibrary:
        path = tmp_path / faker.word() / local_library_name
        path.mkdir(parents=True, exist_ok=True)
        return RestoreLocalLibrary(state=state, library_name=local_library_name, path=path)

    # noinspection PyMethodOverriding
    @pytest.fixture
    def backup_dump(self, model: _BaseRestore, local_tracks: list[LocalTrack], faker: Faker) -> dict[str, Any]:
        model.library.tracks._replace(local_tracks)

        dump = model.library.dump()
        for track in dump["tracks"]:  # change the names before dumping to ensure restore works as expected
            track["name"] = faker.name()

        path = Path(str(model.backup_path) + ".yaml")
        with path.open("w", encoding="utf-8") as file:
            yaml.dump(dump, file)

        for track in dump["tracks"]:
            # dropped in the base package
            track.pop("uri", None)
            track.pop("uris", None)

        return dump

    async def test_restore_tracks(
            self,
            model: RestoreLocalLibrary,
            local_tracks: list[LocalTrack],
            backup_name: str,
            backup_dump: dict[str, Any],
            mock_save: Mock,
            mocker: MockerFixture,
    ):
        model.library.tracks.replace(local_tracks)

        model.include = ("name", "album")
        model.exclude = ("album", "bpm")
        assert model.backup_path

        mock_restore = mocker.spy(type(model.library), "restore_tracks")
        mock_log = mocker.spy(type(model.library), "log_save_tracks_results")

        await model.run()

        mock_restore.assert_called_once_with(
            model.library,
            backup_dump,
            include=model.include,
            exclude=model.exclude,
            dry_run=model.state.dry_run
        )
        mock_log.assert_called_once()


class TestRestoreRemoteLibrary(RestoreTester):
    @pytest.fixture
    def model(self, state: GlobalState, remote_library_name: str, faker: Faker, tmp_path: Path) -> RestoreRemoteLibrary:
        path = tmp_path / faker.word() / remote_library_name
        path.mkdir(parents=True, exist_ok=True)
        return RestoreRemoteLibrary(state=state, library_name=remote_library_name, path=path)

    # noinspection PyMethodOverriding
    @pytest.fixture
    def backup_dump(self, model: _BaseRestore, remote_tracks: list[RemoteTrack], faker: Faker) -> dict[str, Any]:
        model.library.tracks._replace(remote_tracks)

        dump = model.library.dump()

        path = Path(str(model.backup_path) + ".yaml")
        with path.open("w", encoding="utf-8") as file:
            yaml.dump(dump, file)

        return dump

    async def test_run(
            self, model: RestoreRemoteLibrary, backup_name: str, backup_dump: dict[str, Any], mocker: MockerFixture,
    ):
        assert model.backup_path

        mock_restore = mocker.spy(model.library.restore, "func")  # save_state.func
        mock_log = mocker.spy(type(model.library), "log_sync_results")

        await model.run()

        mock_restore.assert_called_once_with(backup_dump, dry_run=model.state.dry_run)
        mock_log.assert_called_once()
