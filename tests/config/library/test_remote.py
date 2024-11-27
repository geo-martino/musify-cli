import typing
from datetime import datetime, timedelta
from random import choice

import pytest
from musify.libraries.remote.core.object import PLAYLIST_SYNC_KINDS

from mocks.remote import RemoteLibraryMock, RemotePlaylistMock, RemoteTrackMock, RemoteAlbumMock, RemoteArtistMock
from mocks.remote import SpotifyLibraryMock, SpotifyPlaylistMock, SpotifyTrackMock, SpotifyArtistMock, SpotifyAlbumMock
from musify_cli.config.library.remote import APIConfig, SpotifyAPIConfig, RemoteNewMusicConfig, RemotePlaylistsSync


class TestRemotePlaylistsSync:

    library_mock: type[RemoteLibraryMock] = SpotifyLibraryMock
    playlist_mock: type[RemotePlaylistMock] = SpotifyPlaylistMock
    track_mock: type[RemoteTrackMock] = SpotifyTrackMock

    @pytest.fixture
    def model(self) -> RemotePlaylistsSync:
        return RemotePlaylistsSync(
            kind=choice(typing.get_args(PLAYLIST_SYNC_KINDS)),
            reload=choice([True, False]),
            filter={}
        )

    @pytest.fixture
    def library(self) -> RemoteLibraryMock:
        return self.library_mock()

    @pytest.fixture
    def playlists(self) -> list[RemotePlaylistMock]:
        """Yields some mock :py:class:`RemotePlaylist` objects as a pytest.fixture."""
        playlists = [self.playlist_mock({}) for _ in range(10)]
        for pl in playlists:
            pl.tracks.extend(self.track_mock({}) for _ in range(50))
        return playlists

    def test_filter_playlists_on_tags(self, model: RemotePlaylistsSync, playlists: list[RemotePlaylistMock]):
        filter_names = [item.name for item in next(pl for pl in playlists if len(pl) > 0)[:2]]
        model.filter = {"name": [name.upper() + "  " for name in filter_names]}

        expected_counts = {}
        for pl in playlists:
            count_remaining = len([item for item in pl if item.name not in filter_names])
            if count_remaining < len(pl):
                expected_counts[pl.name] = count_remaining

        if len(expected_counts) == 0:
            raise Exception("Can't check filter_tags logic, no items to filter out from playlists")

        filtered_playlists = model._filter_playlists(playlists)
        for pl in filtered_playlists:
            if pl.name not in expected_counts:
                continue
            assert len(pl) == expected_counts[pl.name]

    @pytest.mark.parametrize("dry_run", [True, False])
    async def test_sync(
            self,
            model: RemotePlaylistsSync,
            library: RemoteLibraryMock,
            playlists: list[RemotePlaylistMock],
            dry_run: bool,
    ):
        model.filter = {
            "artist": ("bad artist", "nonce"),
            "album": ("unliked album",),
        }

        assert not library.playlists
        await model.run(library=library, playlists=playlists, dry_run=dry_run)

        assert library.sync_args["kind"] == model.kind
        assert library.sync_args["reload"] == model.reload
        assert library.sync_args["dry_run"] == dry_run


class TestNewMusic:

    library_mock: type[RemoteLibraryMock] = SpotifyLibraryMock
    playlist_mock: type[RemotePlaylistMock] = SpotifyPlaylistMock
    album_mock: type[RemoteAlbumMock] = SpotifyAlbumMock
    artist_mock: type[RemoteArtistMock] = SpotifyArtistMock

    @pytest.fixture
    def model(self) -> RemoteNewMusicConfig:
        return RemoteNewMusicConfig(
            name="Super Cool New Music Playlist",
            start=(datetime.now() - timedelta(days=90)).date(),
            end=(datetime.now() - timedelta(days=20)).date(),
        )

    def test_filter_artist_albums_by_date(self, model: RemoteNewMusicConfig):
        library = self.library_mock()

        library.artists.extend(self.artist_mock({}) for _ in range(10))
        for _ in range(100):
            artist = choice(library.artists)
            # noinspection PyTypeChecker
            artist.append(self.album_mock({}))

        albums = [album for artist in library.artists for album in artist.albums]

        expected_counts = sum(
            1 for alb in albums if alb.date is not None and model.start <= alb.date <= model.end
        )
        expected_counts += sum(
            1 for alb in albums
            if alb.month is not None and alb.day is None
            and model.start.month <= alb.month <= model.end.month
        )
        expected_counts += sum(
            1 for alb in albums if alb.month is None and model.start.year <= alb.year <= model.end.year
        )

        assert 0 < expected_counts < len(albums)
        assert len(model._filter_artist_albums_by_date(library)) == expected_counts

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_create_playlist(self, model: RemoteNewMusicConfig):
        pass


class TestRemoteLibrary:
    @pytest.fixture
    def api_model(self) -> APIConfig:
        return SpotifyAPIConfig(
            client_id="",
            client_secret="",
        )
