from collections.abc import Generator
from unittest.mock import Mock

import pytest
from faker import Faker
from mytunes.core._collection.playlist import Playlist
from mytunes.local._collection import LocalLibrary
from pytest_mock import MockerFixture

from mytunes_cli.operations.report.playlist import PlaylistDifferenceReport
from mytunes_cli.state import GlobalState
from tests.operations.report.testers import ReportOperationTester


class TestPlaylistDifferenceReport(ReportOperationTester):
    @pytest.fixture
    def model(
            self, state: GlobalState, local_libraries: dict[str, LocalLibrary], faker: Faker
    ) -> PlaylistDifferenceReport:
        source, target = faker.random_elements(list(local_libraries), length=2, unique=True)
        return PlaylistDifferenceReport(state=state, source_name=source, target_name=target)

    @pytest.fixture(autouse=True)
    def source_playlists(
            self, model: PlaylistDifferenceReport, playlists: list[Playlist], faker: Faker
    ) -> list[Playlist]:
        expected_playlists = faker.random_elements(playlists, unique=True)

        library: LocalLibrary = model.source
        library.playlists.extend(expected_playlists)
        return list(expected_playlists)

    @pytest.fixture(autouse=True)
    def target_playlists(self, model: PlaylistDifferenceReport, playlists: list[Playlist]) -> list[Playlist]:
        library: LocalLibrary = model.target
        library.playlists.extend(playlists)
        return playlists

    @pytest.fixture
    def mock_playlists(
            self, model: PlaylistDifferenceReport, playlists: list[Playlist], mocker: MockerFixture
    ) -> Generator[Mock]:
        mock_playlists = mocker.spy(model, "_get_playlists")
        yield mock_playlists
        mock_playlists.assert_called_once_with(model.source)

    def test_get_results_for_all_source_playlists(
            self, model: PlaylistDifferenceReport, source_playlists: list[Playlist], mock_playlists: Mock
    ):
        results = model._get_results()
        assert len(results) == len(source_playlists)

    def test_get_results_handles_duplicate_names(
            self, model: PlaylistDifferenceReport, source_playlists: list[Playlist], faker: Faker
    ):
        name = faker.word()
        duplicate_count = faker.random_int(2, len(source_playlists))
        for item in faker.random_elements(source_playlists, length=duplicate_count, unique=True):
            item.__dict__["name"] = name

        results = model._get_results()

        assert len({it.name for it in source_playlists}) < len(results)
        assert len(results) == len(source_playlists)
        assert sum(key.startswith(name) for key in results.keys()) == duplicate_count

    def test_get_results_handles_missing_playlists(
            self,
            model: PlaylistDifferenceReport,
            source_playlists: list[Playlist],
            target_playlists: list[Playlist],
            faker: Faker
    ):
        matching_count = faker.random_int(0, len(target_playlists) // 2)
        matching_playlists = faker.random_elements(target_playlists, length=matching_count, unique=True)
        model.target.playlists._replace(matching_playlists)

        results = model._get_results()

        assert len(results) == len(source_playlists)
        assert len(results) > matching_count
        assert len(results) > len(model.target.playlists)
