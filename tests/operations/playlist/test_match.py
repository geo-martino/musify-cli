from abc import ABCMeta
from collections.abc import Generator
from unittest.mock import patch, Mock

import pytest
from faker import Faker
from mytunes.core.playlist import RemotePlaylist
from mytunes.local.playlist import LocalPlaylist
from pytest_mock import MockerFixture

from mytunes_cli.operations.playlist.match import LocalPlaylistMatch, LocalPlaylistSearch
from mytunes_cli.state import GlobalState
from tests.operations.testers import OperationTester


class LocalPlaylistMatchTester(OperationTester, metaclass=ABCMeta):
    @pytest.fixture
    def mock_match(self, model: LocalPlaylistMatch, local_tracks: list[LocalPlaylist]) -> Generator[Mock]:
        with patch.object(type(model), "_match", return_value=local_tracks) as mock_match:
            yield mock_match

    @pytest.fixture
    def mock_save(self, model: LocalPlaylistMatch, mocker: MockerFixture) -> Generator[Mock]:
        with patch.object(model.library, "_run_tasks_async", return_value={}):
            yield mocker.spy(model.library.save_playlists, "func")  # save_state.func


class TestLocalPlaylistMatch(LocalPlaylistMatchTester):
    @pytest.fixture
    @patch.multiple(
        LocalPlaylistMatch,
        __abstractmethods__=set(),
    )
    def model(self, state: GlobalState, local_library_name: str, remote_library_name: str) -> LocalPlaylistMatch:
        return LocalPlaylistMatch(state=state, library_name=local_library_name, api=remote_library_name)

    @pytest.mark.skip(reason="Not supported yet")
    async def test_save(self, model: LocalPlaylistMatch, playlists: list[LocalPlaylist]):
        with patch.object(model.library, "_run_tasks_async", return_value={}) as mock_run:
            await model._save(playlists)

            # only way I can think of to confirm that the save tracks operation still happened on the given tracks
            task_id = mock_run.call_args.kwargs["task_id"]
            task = next(task for task in model.library._progress.tasks if task.id == task_id)
            assert task.total == len(playlists)

        # confirm library's original tracks are restored after operation
        assert model.library.total != len(playlists)


class TestLocalPlaylistSearch(LocalPlaylistMatchTester):
    @pytest.fixture
    def model(self, state: GlobalState, local_library_name: str, remote_library_name: str) -> LocalPlaylistSearch:
        return LocalPlaylistSearch(state=state, library_name=local_library_name, api=remote_library_name)

    def test_match_by_name(
            self,
            model: LocalPlaylistSearch,
            local_playlists: list[LocalPlaylist],
            remote_playlists: list[RemotePlaylist],
            faker: Faker,
    ):
        max_count = min(len(local_playlists), len(remote_playlists))
        matched = faker.random_elements(
            local_playlists, length=faker.random_int(1, max_count), unique=True
        )
        matches = faker.random_elements(remote_playlists, length=len(matched), unique=True)
        for local, remote in zip(matched, matches, strict=True):
            remote.name = local.name

        model.library.playlists.replace(local_playlists)
        model.remote.playlists._replace(remote_playlists)

        result = model._match_by_name()

        assert sorted(result.matched) == sorted(matched)
        assert sorted(result.matches) == sorted(matches)
