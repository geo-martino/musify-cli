from abc import abstractmethod, ABCMeta
from collections.abc import Generator, Sequence
from unittest.mock import patch, Mock, PropertyMock, AsyncMock

import pytest
from faker import Faker
from mytunes.annotation import ResourceModel
from mytunes.core.collection import CollectionModel
from mytunes.core.properties.uri import HasURI
from mytunes.processors.check.result import CheckResult
from mytunes.processors.search import SearchResult
from mytunes.result import Result
from pytest_mock import MockerFixture

from mytunes_cli.operations._match import Match, CollectionCheck, CollectionSearch, ItemSearch, ItemCheck
from mytunes_cli.state import GlobalState
from operations.testers import OperationTester


class MatchTester(OperationTester, metaclass=ABCMeta):
    @abstractmethod
    def results(self, local_tracks: list[HasURI], faker: Faker) -> Result | Sequence[Result]:
        raise NotImplementedError

    @abstractmethod
    def expected(self, results: Result | Sequence[Result]) -> Sequence[ResourceModel]:
        raise NotImplementedError

    @pytest.fixture
    def mock_items(self, model: Match, local_albums: list[CollectionModel]) -> Generator[Mock]:
        with patch.object(
                type(model), "items", return_value=local_albums, new_callable=PropertyMock
        ) as mock_items:
            yield mock_items

    @abstractmethod
    def mock_match(self, results: Result | Sequence[Result]) -> Mock:
        raise NotImplementedError

    @pytest.fixture
    def mock_save(self, model: Match) -> Generator[Mock]:
        with patch.object(model, "_save") as mock_save:
            yield mock_save

    # noinspection PyMethodOverriding
    @pytest.fixture
    def mock_log(self, model: Match, mock_match: Mock, mocker: MockerFixture) -> Generator[Mock]:
        mock_log = mocker.spy(type(model), "log_results")
        yield mock_log
        mock_log.assert_called_once_with(model, mock_match.return_value)


class ItemMatchTester(MatchTester, metaclass=ABCMeta):
    @staticmethod
    async def test_run(
            model: ItemSearch | ItemCheck,
            expected: Sequence[ResourceModel],
            mock_items: Mock,
            mock_match: Mock,
            mock_save: Mock,
            mock_log: Mock,
    ):
        await model.run()

        mock_items.assert_called_once()
        mock_match.assert_called_once_with(mock_items.return_value, name=model.result_key)
        mock_save.assert_called_once_with(expected)


class CollectionMatchTester(MatchTester, metaclass=ABCMeta):
    @staticmethod
    async def test_run(
            model: Match,
            expected: Sequence[ResourceModel],
            mock_items: Mock,
            mock_match: Mock,
            mock_save: Mock,
            mock_log: Mock,
    ):
        await model.run()

        mock_items.assert_called_once()
        mock_match.assert_called_once_with(mock_items.return_value)
        mock_save.assert_called_once_with(expected)


class TestItemSearch(ItemMatchTester):
    @pytest.fixture
    @patch.multiple(
        ItemSearch,
        __abstractmethods__=set(),
    )
    def model(self, state: GlobalState, remote_library_name: str) -> ItemSearch:
        # noinspection PyAbstractClass
        return ItemSearch(state=state, api=remote_library_name)

    @pytest.fixture
    def results(self, local_tracks: list[HasURI], faker: Faker) -> SearchResult:
        matched = faker.random_elements(local_tracks, unique=True)
        unmatched = [track for track in local_tracks if track not in matched]
        return SearchResult(name=faker.name(), matched=matched, matches=matched, unmatched=unmatched)

    @pytest.fixture
    def expected(self, results: SearchResult) -> Sequence[ResourceModel]:
        return results.matched

    @pytest.fixture
    def mock_items(self, model: ItemSearch, local_tracks: list[ResourceModel]) -> Generator[Mock]:
        with patch.object(
                type(model), "items", return_value=local_tracks, new_callable=PropertyMock
        ) as mock_items:
            yield mock_items

    @pytest.fixture
    def mock_match(self, results: SearchResult) -> Generator[Mock]:
        with patch.object(ItemSearch, "search_many", return_value=results) as mock_search:
            yield mock_search

    @pytest.fixture(autouse=True)
    def mock_result_key(
            self, model: Match, local_albums: list[CollectionModel], faker: Faker
    ) -> Generator[Mock | None]:
        with patch.object(
                type(model), "result_key", return_value=faker.word(), new_callable=PropertyMock
        ) as mock_key:
            yield mock_key


class TestCollectionSearch(CollectionMatchTester):
    @pytest.fixture
    @patch.multiple(
        CollectionSearch,
        __abstractmethods__=set(),
    )
    def model(self, state: GlobalState, remote_library_name: str) -> CollectionSearch:
        # noinspection PyAbstractClass
        return CollectionSearch(state=state, api=remote_library_name)

    @pytest.fixture
    def results(self, local_tracks: list[HasURI], faker: Faker) -> tuple[SearchResult, ...]:
        matched = faker.random_elements(local_tracks, unique=True)
        unmatched = [track for track in local_tracks if track not in matched]
        return SearchResult(name=faker.name(), matched=matched, matches=matched, unmatched=unmatched),

    @pytest.fixture
    def expected(self, results: Sequence[SearchResult]) -> tuple[ResourceModel, ...]:
        return tuple(item for result in results for item in result.matched)

    @pytest.fixture
    def mock_match(self, results: Sequence[SearchResult]) -> Generator[Mock]:
        with patch.object(CollectionSearch, "search_many", return_value=results) as mock_search:
            yield mock_search


class TestItemCheck(ItemMatchTester):
    @pytest.fixture
    @patch.multiple(
        ItemCheck,
        __abstractmethods__=set(),
    )
    def model(self, state: GlobalState, remote_library_name: str) -> ItemCheck:
        # noinspection PyAbstractClass
        return ItemCheck(state=state, api=remote_library_name)

    @pytest.fixture
    def results(self, local_tracks: list[HasURI], faker: Faker) -> CheckResult:
        changed = faker.random_elements(local_tracks, unique=True)
        unavailable = faker.random_elements([track for track in local_tracks if track not in changed], unique=True)
        return CheckResult(name=faker.name(), changed=changed, unavailable=unavailable)

    @pytest.fixture
    def expected(self, results: CheckResult) -> tuple[ResourceModel, ...]:
        return tuple(list(results.changed) + list(results.unavailable))

    @pytest.fixture
    def mock_items(self, model: ItemCheck, local_tracks: list[ResourceModel]) -> Generator[Mock]:
        with patch.object(
                type(model), "items", return_value=local_tracks, new_callable=PropertyMock
        ) as mock_items:
            yield mock_items

    @pytest.fixture
    def mock_match(self, results: CheckResult) -> Generator[Mock]:
        with patch.object(ItemCheck, "check", return_value=results, new_callable=AsyncMock) as mock_check:
            yield mock_check

    @pytest.fixture(autouse=True)
    def mock_result_key(
            self, model: Match, local_albums: list[CollectionModel], faker: Faker
    ) -> Generator[Mock | None]:
        with patch.object(
                type(model), "result_key", return_value=faker.word(), new_callable=PropertyMock
        ) as mock_key:
            yield mock_key


class TestCollectionCheck(CollectionMatchTester):
    @pytest.fixture
    @patch.multiple(
        CollectionCheck,
        __abstractmethods__=set(),
    )
    def model(self, state: GlobalState, remote_library_name: str) -> CollectionCheck:
        # noinspection PyAbstractClass
        return CollectionCheck(state=state, api=remote_library_name)

    @pytest.fixture
    def results(self, local_tracks: list[HasURI], faker: Faker) -> tuple[CheckResult, ...]:
        changed = faker.random_elements(local_tracks, unique=True)
        unavailable = faker.random_elements([track for track in local_tracks if track not in changed], unique=True)
        return (CheckResult(name=faker.name(), changed=changed, unavailable=unavailable),)

    @pytest.fixture
    def expected(self, results: Sequence[CheckResult]) -> Sequence[ResourceModel]:
        return tuple(item for result in results for item in list(result.changed) + list(result.unavailable))

    @pytest.fixture
    def mock_match(self, results: Sequence[CheckResult]) -> Generator[Mock]:
        with patch.object(
                CollectionCheck, "check_on_playlists", return_value=results, new_callable=AsyncMock
        ) as mock_check:
            yield mock_check
