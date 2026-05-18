from abc import ABCMeta
from collections.abc import Generator
from datetime import date
from unittest.mock import patch, MagicMock, AsyncMock, Mock, PropertyMock

import pytest
from faker import Faker
from mytunes.core.album import AlbumCollection
from mytunes.core.api.playlist import PlaylistLibraryEndpoints
from mytunes.core.collection import SyncRemoteResult
from mytunes.core.playlist import MutablePlaylist, RemoteMutablePlaylist
from mytunes.core.properties.date import SparseDate
from mytunes.core.sequence import MutableUniqueSequence
from mytunes.core.track import Track, RemoteTrack
from mytunes.local.album import LocalAlbumCollection
from mytunes.local.artist import LocalArtistCollection
from pytest_mock import MockerFixture

from conftest import remote_library_name
from mytunes_cli.operations.playlist.create import CreateRemotePlaylistOperation, NewMusicPlaylist
from mytunes_cli.state import GlobalState
from operations.testers import OperationTester
from utils import split_list


class CreateRemotePlaylistTester(OperationTester, metaclass=ABCMeta):
    @pytest.fixture
    def playlist(self, faker: Faker) -> MagicMock:
        playlist = MagicMock(spec=RemoteMutablePlaylist)
        playlist.name = faker.name()
        playlist.tracks = MutableUniqueSequence()
        return playlist

    @pytest.fixture(autouse=True)
    def mock_create_playlist(
            self, playlist: RemoteMutablePlaylist
    ) -> Generator[Mock]:
        with patch.object(
                PlaylistLibraryEndpoints, "get_or_create", return_value=playlist, new_callable=AsyncMock
        ) as mock_create:
            yield mock_create

    @pytest.fixture(autouse=True)
    def mock_sync_playlist(self, playlist: MutablePlaylist, faker: Faker) -> Mock:
        result = SyncRemoteResult(
            name=playlist.name,
            start=faker.random_int(),
            added=faker.random_int(),
            removed=faker.random_int(),
            unchanged=faker.random_int(),
            difference=faker.random_int(),
            final=faker.random_int(),
        )

        mock_sync = AsyncMock(return_value=result)
        playlist.sync_items = mock_sync
        return mock_sync


class TestCreateRemotePlaylist(CreateRemotePlaylistTester):
    @pytest.fixture
    @patch.multiple(
        CreateRemotePlaylistOperation,
        __abstractmethods__=set(),
        run=MagicMock(),
    )
    def model(self, state: GlobalState, remote_library_name: str, faker: Faker) -> CreateRemotePlaylistOperation:
        return CreateRemotePlaylistOperation(
            state=state,
            name=faker.name(),
            library_name=remote_library_name
        )

    @pytest.fixture(autouse=True)
    def mock_tracks(
            self, model: CreateRemotePlaylistOperation, remote_tracks: list[RemoteTrack]
    ) -> Generator[list[RemoteTrack]]:
        with patch.object(
                CreateRemotePlaylistOperation, "tracks", return_value=remote_tracks, new_callable=PropertyMock
        ):
            yield remote_tracks

    async def test_create_playlist(
            self,
            model: CreateRemotePlaylistOperation,
            playlist: RemoteMutablePlaylist,
            remote_tracks: list[RemoteTrack],
            mock_sync_playlist: Mock,
    ):
        result = await model._create_playlist()

        assert result.name == playlist.name
        assert playlist.tracks == remote_tracks

        mock_sync_playlist.assert_called_once_with(
            model.library.api,
            kind="sync",
            sync_filter=model.library.sync_filter,
            dry_run=model.state.dry_run
        )

    async def test_run(
            self,
            model: NewMusicPlaylist,
            playlist: RemoteMutablePlaylist,
            remote_tracks: list[RemoteTrack],
            mocker: MockerFixture,
    ):
        mock_create = mocker.spy(model, "_create_playlist")

        await model.run()

        assert playlist.tracks == remote_tracks
        mock_create.assert_called_once()


class TestNewMusicPlaylist(CreateRemotePlaylistTester):
    @pytest.fixture
    def model(self, state: GlobalState, remote_library_name: str, faker: Faker) -> NewMusicPlaylist:
        return NewMusicPlaylist(
            state=state,
            name=faker.name(),
            library_name=remote_library_name
        )

    @pytest.fixture
    def albums(
            self,
            model: NewMusicPlaylist,
            local_albums: list[LocalAlbumCollection],
            local_tracks: list[Track],
            faker: Faker,
    ) -> list[LocalAlbumCollection]:
        for albums in split_list(local_albums, faker.random_int(1, len(local_albums))):
            artist_name = faker.name()

            for album in albums:
                tracks = faker.random_elements(local_tracks) if faker.boolean() else []
                for track in tracks:
                    track.album = album

                album.artist = artist_name
                album.tracks[:] = tracks

                year = int(faker.year())
                month = faker.random_element((faker.month(), None))
                day = faker.random_element((faker.day_of_month(), None))
                album.released_at = SparseDate(year=year, month=month, day=day if month else None)

            artist = LocalArtistCollection(name=artist_name, albums=albums)
            model.library.artists.append(artist)

        return local_albums

    @staticmethod
    def _get_expected_albums(albums: list[AlbumCollection]) -> list[AlbumCollection]:
        expected = [album for album in albums if album.total]
        return sorted(expected, key=lambda album: album.released_at, reverse=True)

    def test_albums(
            self, model: NewMusicPlaylist, albums: list[AlbumCollection]
    ):
        assert model.albums == self._get_expected_albums(albums)

    def test_albums_filters_on_dates(
            self, model: NewMusicPlaylist, albums: list[AlbumCollection], faker: Faker
    ):
        from_date = min(album.released_at for album in faker.random_elements(albums, unique=True))
        to_date = max(album.released_at for album in faker.random_elements(albums, unique=True))
        model.from_date = date(year=from_date.year, month=from_date.month or 1, day=from_date.day or 1)
        model.to_date = date(year=to_date.year, month=to_date.month or 1, day=to_date.day or 1)

        filtered_albums = [album for album in albums if from_date <= album.released_at <= to_date]

        assert model.albums == self._get_expected_albums(filtered_albums)

    def test_tracks(self, model: NewMusicPlaylist, albums: list[AlbumCollection], faker: Faker):
        albums = faker.random_elements(albums, unique=True)

        with patch.object(NewMusicPlaylist, "albums", return_value=albums, new_callable=PropertyMock):
            assert model.tracks == [track for album in albums for track in album.tracks]
