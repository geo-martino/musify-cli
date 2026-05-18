from collections.abc import Generator
from unittest.mock import patch, Mock

import pytest
from mytunes.local.library import LocalLibrary
from pytest_mock import MockerFixture

from mytunes_cli.operations._base import TagOperation
from mytunes_cli.state._decorators import save_state


@pytest.fixture
def mock_save(model: TagOperation, local_library: LocalLibrary, mocker: MockerFixture) -> Generator[Mock]:
    if isinstance(local_library.save_tracks, save_state):
        mock_save = mocker.spy(local_library.save_tracks, "func")
    else:
        mock_save = mocker.spy(type(local_library), "save_tracks")

    with patch.object(local_library, "_run_tasks_async", return_value={}) as mock_run:
        yield mock_run

    if not model.save or not local_library.tracks:
        mock_save.assert_not_called()
        return

    assert mock_save.call_args.kwargs == dict(
        include=model.include,
        exclude=model.exclude,
        replace=model.replace,
        dry_run=model.state.dry_run,
    )
