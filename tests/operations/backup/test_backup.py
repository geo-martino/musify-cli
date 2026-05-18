from pathlib import Path

import pytest
import yaml
from faker import Faker
from mytunes.core.library import Library
from pytest_mock import MockerFixture

from mytunes_cli.operations.backup.backup import Backup
from mytunes_cli.state import GlobalState
from tests.operations.testers import OperationTester


class TestBackup(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState, library_name: str, faker: Faker) -> Backup:
        return Backup(state=state, library_name=library_name, path=Path(faker.word()))

    def test_paths(self, model: Backup):
        assert model.backup_dir.name == model.library_name
        assert model.backup_path.name == model.backup_filename
        assert model.backup_path.parent.name == model.library_name

    def test_filename(self, model: Backup, faker: Faker):
        model.key = None
        assert model.backup_filename == model.state.timestamp

        model.key = faker.word()
        assert model.backup_filename.startswith(model.state.timestamp)
        assert model.key in model.backup_filename

    async def test_save_yaml(self, model: Backup, library: Library):
        dump = library.dump()
        expected_file_path = Path(str(model.backup_path) + ".yaml")

        await model._save_yaml(dump)
        assert expected_file_path.is_file()

        with expected_file_path.open("r", encoding="utf-8") as file:
            assert yaml.safe_load(file) == dump

    async def test_run(self, model: Backup, library: Library, mocker: MockerFixture):
        mock_save = mocker.spy(model, "_save_yaml")
        dump = library.dump()

        await model.run()
        mock_save.assert_called_once_with(dump)
