from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from faker import Faker

from mytunes_cli.operations.backup._base import _BaseOperation
from mytunes_cli.state import GlobalState
from operations.testers import OperationTester


class TestBaseOperation(OperationTester):
    # noinspection PyAbstractClass
    @pytest.fixture
    @patch.multiple(
        _BaseOperation,
        __abstractmethods__=set(),
        run=MagicMock(),
    )
    def model(self, state: GlobalState, library_name: str, faker: Faker) -> _BaseOperation:
        return _BaseOperation(state=state, library_name=library_name, path=Path(faker.word()))

    @pytest.fixture(autouse=True)
    def filename(self, faker: Faker) -> Generator[str]:
        filename = faker.word()
        with patch.object(
                _BaseOperation, "backup_filename", return_value=filename, new_callable=PropertyMock, create=True
        ):
            yield filename

    def test_paths_with_absolute_path(self, model: _BaseOperation, faker: Faker):
        path = Path(faker.file_path()).parent / Path(*faker.words())

        model.path = path
        assert model.backup_dir == path / model.library_name
        assert model.backup_path == path / model.library_name / model.backup_filename

        model.path = path / model.library_name
        assert model.backup_dir == path / model.library_name
        assert model.backup_path == path / model.library_name / model.backup_filename

    def test_paths_with_relative_path(self, model: _BaseOperation, faker: Faker):
        model.path = Path(faker.word())
        expected = model.state.paths.application / model.path / model.library_name

        assert model.backup_dir == expected
        assert model.backup_path == expected / model.backup_filename
