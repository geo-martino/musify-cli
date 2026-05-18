from abc import ABCMeta
from unittest.mock import patch, MagicMock, Mock

import pytest
from faker import Faker
from mytunes.core.library import RemoteLibrary
from mytunes.local.library import LocalLibrary
from mytunes.local.track import LocalTrack

from mytunes_cli.operations._base import RemoteAPIOperation, TagOperation, TAGS_SAVE
from mytunes_cli.state import GlobalState
from operations.testers import OperationTester


class TestRemoteAPIOperation(OperationTester, metaclass=ABCMeta):
    @patch.multiple(
        RemoteAPIOperation,
        __abstractmethods__=set(),
        run=MagicMock(),
    )
    def test_get_api_from_library(self, remote_libraries: dict[str, RemoteLibrary], state: GlobalState, faker: Faker):
        name, library = faker.random_element(remote_libraries.items())
        model = RemoteAPIOperation(api=name, state=state)
        assert model.api is library.api


class TestTagOperation(OperationTester):
    @pytest.fixture
    @patch.multiple(
        TagOperation,
        __abstractmethods__=set(),
        run=MagicMock(),
    )
    def model(self, state: GlobalState, faker: Faker) -> TagOperation:
        include = faker.random_elements(TAGS_SAVE, unique=True)
        exclude = faker.random_elements(TAGS_SAVE, unique=True)
        return TagOperation(state=state, include=include, exclude=exclude, replace=faker.boolean())

    @staticmethod
    async def test_save_library(
            model: TagOperation, local_library: LocalLibrary, local_tracks: list[LocalTrack], mock_save: Mock
    ):
        model.save = True
        local_library.tracks.replace(local_tracks)

        await model._save_tracks(local_library)
        # assertions handled by mock_save teardown

    @staticmethod
    async def test_no_save(
            model: TagOperation,
            local_library: LocalLibrary,
            local_tracks: list[LocalTrack],
            mock_save: Mock,
    ):
        model.save = False
        local_library.tracks.replace(local_tracks)

        await model._save_tracks(local_library)
        # assertions handled by mock_save teardown

    @staticmethod
    async def test_no_tracks(
            model: TagOperation,
            local_library: LocalLibrary,
            mock_save: Mock,
    ):
        model.save = True
        local_library.tracks.clear()

        await model._save_tracks(local_library)
        # assertions handled by mock_save teardown

    async def test_save_tracks(self, model: TagOperation, local_library: LocalLibrary, local_tracks: list[LocalTrack]):
        with patch.object(local_library, "_run_tasks_async", return_value={}) as mock_run:
            await model._save_tracks(local_library, local_tracks)

            # only way I can think of to confirm that the save tracks operation still happened on the given tracks
            task_id = mock_run.call_args.kwargs["task_id"]
            task = next(task for task in local_library._progress.tasks if task.id == task_id)
            assert task.total == len(local_tracks)

        # confirm library's original tracks are restored after operation
        assert local_library.total != len(local_tracks)
