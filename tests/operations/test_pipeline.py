from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import yaml
from faker import Faker
from pydantic_settings import CliApp
from pytest_mock import MockerFixture

from mytunes_cli.operations import Operation
from mytunes_cli.operations.pipeline import Pipeline
from mytunes_cli.printer import Printer
from mytunes_cli.state import GlobalState
from operations.testers import OperationTester
from utils import patch_input


class TestPipeline(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState) -> Pipeline:
        return Pipeline(state=state, printer=Printer(state=state))

    @pytest.fixture
    def config(self, local_library_name: str, remote_library_name: str) -> list[dict[str, Any]]:
        return [
            {"backup": {"local": {"library": local_library_name}}},
            {"pause": {}},
            {"print": {"api": remote_library_name}},
        ]

    @pytest.fixture
    def config_path(self, config: list[dict[str, Any]], faker: Faker, tmp_path: Path) -> Path:
        config_path = tmp_path.joinpath(faker.file_name(extension="yml"))
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with config_path.open("w") as file:
            file.write(yaml.dump(config))

        return config_path

    @pytest.fixture
    def mock_run(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(CliApp, "run")

    @pytest.fixture
    def mock_from_config(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(Pipeline, "from_config")

    @pytest.fixture
    def mock_from_input(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(Pipeline, "from_input")

    def test_load_from_file(self, state: GlobalState, config: list[dict[str, Any]], config_path: Path):
        model = Pipeline(operations=config_path, state=state, printer=Printer(state=state))
        assert len(model.operations) == len(config)  # just checking that the number of operations to run matches

    async def test_from_config(
            self, state: GlobalState, config_path: Path, mock_from_config: Mock, mock_from_input: Mock
    ):
        model = Pipeline(operations=config_path, state=state, printer=Printer(state=state))

        with patch.object(Operation, "cli_cmd") as mock_operation:
            await model.run()
            assert mock_operation.call_count == len(model.operations)

        mock_from_config.assert_called_once()
        mock_from_input.assert_not_called()

    async def test_from_input_quits(self, model: Pipeline, mock_run: Mock):
        with patch_input(["q"]):
            await model.run()
        mock_run.assert_not_called()

    async def test_from_input_skips_on_bad_commands(self, model: Pipeline, mock_run: Mock, faker: Faker):
        inputs = [faker.sentence() for _ in range(faker.random_int(1, 10))]
        with patch_input(inputs + ["q"]):
            await model.run()
        assert mock_run.call_count == len(inputs)
