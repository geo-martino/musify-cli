from collections.abc import Generator
from copy import deepcopy
from unittest.mock import patch, Mock

import pytest
from faker import Faker
from mytunes.local.album import LocalAlbumCollection
from mytunes.local.track import LocalTrack

from mytunes_cli.operations.report.tags import MissingTagReport
from mytunes_cli.state import GlobalState
from operations.report.testers import ReportOperationTester


class TestMissingTagResult(ReportOperationTester):
    @pytest.fixture
    def model(self, state: GlobalState, local_library_name: str) -> MissingTagReport:
        return MissingTagReport(state=state, library_name=local_library_name)

    @pytest.fixture(autouse=True)
    def missing_tag_albums(
            self,
            model: MissingTagReport,
            local_albums: list[LocalAlbumCollection],
            local_tracks: list[LocalTrack],
            faker: Faker,
    ) -> list[LocalAlbumCollection]:
        model.tags = ("comments", "bpm")

        missing_tag_albums: list[LocalAlbumCollection] = []

        for album in local_albums:
            tracks = faker.random_elements(local_tracks, unique=True)
            album.tracks.replace(deepcopy(tracks))

            for track in album.tracks:
                track.bpm = faker.random_int(80, 150) if faker.boolean() else None
                track.comments = faker.pylist(value_types=[str]) if faker.boolean() else []

                if album not in missing_tag_albums and (not track.bpm or not track.comments):
                    missing_tag_albums.append(album)

        return missing_tag_albums

    @pytest.fixture
    def mock_albums(self, model: MissingTagReport, local_albums: list[LocalAlbumCollection]) -> Generator[Mock]:
        with patch.object(model, "_get_albums", return_value=local_albums) as mock_albums:
            yield mock_albums

        mock_albums.assert_called_once_with(model.library)

    def test_get_results_on_any_missing(
            self,
            model: MissingTagReport,
            local_albums: list[LocalAlbumCollection],
            missing_tag_albums: list[LocalAlbumCollection],
    ):
        results = model._get_results(local_albums)
        assert len(results) == len(missing_tag_albums)

    def test_get_results_on_all_missing(
            self,
            model: MissingTagReport,
            local_albums: list[LocalAlbumCollection],
            missing_tag_albums: list[LocalAlbumCollection],
    ):
        model.match_all = True

        results = model._get_results(local_albums)
        assert len(results) < len(missing_tag_albums)

    def test_get_results_handles_duplicate_names(
            self,
            model: MissingTagReport,
            local_albums: list[LocalAlbumCollection],
            missing_tag_albums: list[LocalAlbumCollection],
            faker: Faker
    ):
        name = faker.word()
        duplicate_count = faker.random_int(2, len(missing_tag_albums))
        for item in faker.random_elements(missing_tag_albums, length=duplicate_count, unique=True):
            item.__dict__["name"] = name

        results = model._get_results(local_albums)

        assert len({it.name for it in missing_tag_albums}) < len(results)
        assert len(results) == len(missing_tag_albums)
        assert sum(key.startswith(name) for key in results.keys()) == duplicate_count

    # noinspection PyMethodOverriding
    async def test_run(self, model: MissingTagReport, mock_albums: Mock, mock_log: Mock):
        await super().test_run(model, mock_log)
