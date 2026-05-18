from abc import ABCMeta, abstractmethod
from collections.abc import Generator
from unittest.mock import Mock

import pytest
from pydantic import TypeAdapter
from pytest_mock import MockerFixture

from mytunes_cli.operations import Operation
from mytunes_cli.operations._match import Match


class OperationTester(metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.BaseModel` implementations"""
    @abstractmethod
    def model(self, **kwargs) -> Operation:
        """Fixture for the models to test"""
        raise NotImplementedError

    @pytest.fixture
    def adapter(self, model: Operation) -> TypeAdapter:
        """Fixture for the type adapter to use when validating python objects for this models"""
        return TypeAdapter(model.__class__)


class MatchTester(OperationTester):

    @abstractmethod
    def mock_match(self, model: Match, items: list) -> Generator[Mock]:
        raise NotImplementedError

    @abstractmethod
    def mock_save(self, model: Match, mocker: MockerFixture) -> Generator[Mock]:
        raise NotImplementedError

    @staticmethod
    async def test_run_with_save(model: Match, mock_match: Mock, mock_save: Mock):
        model.save = True

        await model.run()

        mock_match.assert_called_once()
        mock_save.assert_called_once()

    @staticmethod
    async def test_run_no_save(model: Match, mock_match: Mock, mock_save: Mock):
        model.save = True
        mock_match.return_value = {}

        await model.run()

        mock_match.assert_called_once()
        mock_save.assert_not_called()
