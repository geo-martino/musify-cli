from abc import ABCMeta
from unittest.mock import Mock, patch

import pytest
from pytest_mock import MockerFixture

from mytunes_cli.operations.report._base import ReportOperation
from tests.operations.testers import OperationTester


class ReportOperationTester(OperationTester, metaclass=ABCMeta):
    @pytest.fixture
    def mock_log(self, model: ReportOperation, mocker: MockerFixture) -> Mock:
        mock_log = mocker.patch.object(model, "_log_results")
        return mock_log

    async def test_run(self, model: ReportOperation, mock_log: Mock):
        await model.run()
        mock_log.assert_called_once()

    @staticmethod
    async def test_run_skips_log(model: ReportOperation, mock_log: Mock):
        with patch.object(model, "_get_results", return_value={}):
            await model.run()

        mock_log.assert_not_called()
