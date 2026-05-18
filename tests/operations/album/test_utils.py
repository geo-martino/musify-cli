from collections.abc import Generator
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from mytunes.annotation import Playlist, Album, Track
from mytunes.local._collection import LocalAlbumCollection
from mytunes.processors.download import StoreManager, GeneralAudioStore
from pytest_mock import MockerFixture

from mytunes_cli.operations.album.utils import AlbumDownload
from mytunes_cli.state import GlobalState
from tests.operations.testers import OperationTester


class TestAlbumDownload(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState, remote_library_name: str) -> AlbumDownload:
        return AlbumDownload(
            state=state,
            library_name=remote_library_name,
            stores=[GeneralAudioStore(url="https://music.example.com/search?query={}")],
            fields=["name"],
        )

    @pytest.fixture(autouse=True)
    def albums(
            self, local_albums: list[LocalAlbumCollection], local_tracks: list[Track], faker: Faker,
    ) -> list[LocalAlbumCollection]:
        for album in local_albums:
            tracks = deepcopy(faker.random_elements(local_tracks))
            for track in tracks:
                track.album = album

            album.tracks[:] = tracks

        return local_albums

    @pytest.fixture(autouse=True)
    def playlists(self, playlists: list[Playlist], albums: list[LocalAlbumCollection]) -> list[Playlist]:
        # add all tracks to each playlist to ensure all albums are processed
        tracks = [track for album in albums for track in album.tracks]
        for playlist in playlists:
            playlist.tracks[:] = tracks
        return playlists

    @pytest.fixture
    def mock_playlists(
            self, model: AlbumDownload, playlists: list[Playlist], mocker: MockerFixture
    ) -> Generator[Mock]:
        model.library.playlists.extend(playlists)

        mock_playlists = mocker.spy(model, "_get_playlists")
        yield mock_playlists
        mock_playlists.assert_called_once_with(model.library)

    async def test_run(self, model: AlbumDownload, albums: list[Album], mock_playlists: Mock):
        with patch.object(StoreManager, "open_sites_for_items") as mock_open_sites:
            await model.run()
            mock_open_sites.assert_called_once_with(albums)
