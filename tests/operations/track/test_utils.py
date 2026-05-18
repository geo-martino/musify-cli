from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
from mytunes.annotation import Playlist
from mytunes.processors.download import StoreManager, GeneralAudioStore
from pytest_mock import MockerFixture

from mytunes_cli.operations.track.utils import Download
from mytunes_cli.state import GlobalState
from tests.operations.testers import OperationTester


class TestTrackDownload(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState, remote_library_name: str) -> Download:
        return Download(
            state=state,
            library_name=remote_library_name,
            stores=[GeneralAudioStore(url="https://music.example.com/search?query={}")],
            fields=["name"],
        )

    @pytest.fixture
    def mock_playlists(self, model: Download, playlists: list[Playlist], mocker: MockerFixture) -> Generator[Mock]:
        model.library.playlists.extend(playlists)

        mock_playlists = mocker.spy(model, "_get_playlists")
        yield mock_playlists
        mock_playlists.assert_called_once_with(model.library)

    async def test_run(self, model: Download, playlists: list[Playlist], mock_playlists: Mock):
        with patch.object(StoreManager, "open_sites_for_collections") as mock_open_sites:
            await model.run()
            mock_open_sites.assert_called_once_with(playlists)
