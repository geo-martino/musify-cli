from collections.abc import Generator
from typing import get_args
from unittest.mock import MagicMock, patch, Mock, AsyncMock

import pytest
from faker import Faker
from mytunes.core.api import ItemReadEndpoints, Endpoints
from mytunes.core.api.search import SearchEndpoints, HasSearchEndpoints
from mytunes.core.properties.uri import URI
from mytunes.exception import APIError
from mytunes.processors.formatter import FIELDS, ModelFormatter
from pytest_mock import MockerFixture

from mytunes_cli.operations.utils import Pause, Print
from mytunes_cli.state import GlobalState
from operations.testers import OperationTester
from remote import SimpleURI
from utils import patch_input


class TestPause(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState) -> Pause:
        return Pause(state=state)

    async def test_run(self, model: Pause):
        inputs = iter([""])
        with patch_input(inputs):
            await model.run()

        with pytest.raises(StopIteration):
            next(inputs)


class TestPrint(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState, remote_library_name: str, uri: URI) -> Print:
        return Print(state=state, api=remote_library_name, type=uri.type, always_prompt=False)

    @pytest.fixture
    def uri(self, faker: Faker) -> URI:
        kind = faker.random_element(("track", "artist", "album"))
        return SimpleURI.create_random(kind)

    @pytest.fixture
    def mock_format(self, mocker: MockerFixture) -> Mock:
        mock_format = mocker.spy(ModelFormatter, "format")
        return mock_format

    @pytest.fixture(autouse=True)
    def mock_get(self, model: Print, uri: URI) -> Generator[Mock]:
        mock_endpoint = AsyncMock(return_value=None)

        def _get_endpoints(*_, **__) -> Mock | None:
            mock = MagicMock(spec=ItemReadEndpoints)
            mock.get = mock_endpoint
            return mock

        with patch.object(ItemReadEndpoints, "validate_api", side_effect=_get_endpoints):
            yield mock_endpoint

    @pytest.fixture(autouse=True)
    def mock_query(self, model: Print, uri: URI) -> Generator[Mock]:
        mock_endpoint = AsyncMock(return_value=None)

        def _get_endpoints(*_, **__) -> Mock | None:
            mock = MagicMock(spec=SearchEndpoints)
            mock.query = mock_endpoint
            mock.supported_search_types = [uri.type]
            return mock

        with patch.object(HasSearchEndpoints, "validate_api", side_effect=_get_endpoints):
            yield mock_endpoint

    def test_validate_from_fields(self, remote_library_name: str, state: GlobalState, faker: Faker):
        fields = faker.random_elements(get_args(FIELDS))

        model = Print(state=state, api=remote_library_name, formatter=fields)
        assert model.formatter.fields == fields
        assert model.formatter.header

    async def test_not_always_prompt(self, model: Print, uri: URI, mock_get: Mock, mock_query: Mock, mock_format: Mock):
        model.always_prompt = False

        inputs = [uri, uri, uri, ""]
        mock_get.return_value = uri

        with patch_input(inputs) as mock_input:
            await model.run()

            mock_input.assert_called_once()
            mock_get.assert_called_once_with(uri)
            mock_query.assert_not_called()
            mock_format.assert_called_once()

    async def test_always_prompt(self, model: Print, uri: URI, mock_get: Mock, mock_query: Mock, mock_format: Mock):
        model.always_prompt = True

        inputs = [uri, uri, uri, ""]
        mock_get.return_value = uri

        with patch_input(inputs) as mock_input:
            await model.run()

            assert mock_input.call_count == 4
            assert mock_get.call_count == 3
            mock_query.assert_not_called()
            assert mock_format.call_count == 3

    async def test_quit(self, model: Print, uri: URI, mock_get: Mock, mock_query: Mock, mock_format: Mock):
        inputs = ["query me", "also query me", "", "do not query me"]

        with patch_input(inputs) as mock_input:
            await model.run()

            assert mock_input.call_count == 3
            mock_get.assert_not_called()
            assert mock_query.call_count == 2
            mock_format.assert_not_called()

    async def test_invalid_api(self, model: Print, uri: URI, mock_format: Mock):
        inputs = [uri, "search for me", ""]

        with patch_input(inputs) as mock_input, patch.object(Endpoints, "validate_api", side_effect=APIError):
            await model.run()

            assert mock_input.call_count == 3
            mock_format.assert_not_called()

    async def test_from_uri(self, model: Print, uri: URI, mock_get: Mock, mock_query: Mock, mock_format: Mock):
        inputs = [uri]
        mock_get.return_value = uri

        with patch_input(inputs) as mock_input:
            await model.run()

            mock_input.assert_called_once()
            mock_get.assert_called_once()
            mock_query.assert_not_called()
            mock_format.assert_called_once()

    async def test_from_search(self, model: Print, uri: URI, mock_get: Mock, mock_query: Mock, mock_format: Mock):
        inputs = ["search for me"]
        mock_query.return_value = {uri.type: [uri]}

        with patch_input(inputs) as mock_input:
            await model.run()

            mock_input.assert_called_once()
            mock_get.assert_not_called()
            mock_query.assert_called_once()
            mock_format.assert_called_once()

    async def test_from_search_no_type(self, model: Print, uri: URI, mock_get: Mock, mock_query: Mock, mock_format: Mock):
        model.type = None

        inputs = ["search for me", "invalid type", "invalid type", "invalid type", uri.type]
        mock_query.return_value = {uri.type: [uri]}

        with patch_input(inputs) as mock_input:
            await model.run()

            assert mock_input.call_count == 5
            mock_get.assert_not_called()
            mock_query.assert_called_once()
            mock_format.assert_called_once()

    async def test_get_collection_items(self, model: Print, uri: URI, mock_get: Mock, mock_query: Mock, mock_format: Mock):
        pass  # TODO
