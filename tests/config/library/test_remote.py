import typing
from random import choice, randrange

import pytest
from aiorequestful.cache.backend import CACHE_TYPES
from musify.field import TagFields
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.core.object import PLAYLIST_SYNC_KINDS
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.processors.match import ItemMatcher
from pydantic import ValidationError

from mocks.remote import RemoteLibraryMock, RemotePlaylistMock, RemoteTrackMock, RemoteAlbumMock, RemoteArtistMock
from mocks.remote import SpotifyLibraryMock, SpotifyPlaylistMock, SpotifyTrackMock, SpotifyArtistMock, SpotifyAlbumMock
from musify_cli.config.library.remote import APIConfig, SpotifyAPIConfig, RemoteNewMusicConfig, RemotePlaylistsSync, \
    RemoteItemCheckerConfig, RemoteItemSearcherConfig, RemoteItemDownloadConfig, APIHandlerRetry, APIHandlerWait, \
    APICacheConfig, local_caches, APIHandlerConfig, RemoteLibraryConfig, SpotifyLibraryConfig, RemotePlaylistsConfig
from utils import random_str


class TestRemoteItemCheckerConfig:

    @pytest.fixture
    def model(self) -> RemoteItemCheckerConfig:
        return RemoteItemCheckerConfig(
            interval=randrange(10, 20),
            allow_karaoke=choice([True, False]),
        )

    def test_create(self, model: RemoteItemCheckerConfig, matcher: ItemMatcher, spotify_factory: RemoteObjectFactory):
        checker = model.create(factory=spotify_factory, matcher=matcher)

        assert checker.interval == model.interval
        assert checker.allow_karaoke is model.allow_karaoke
        assert checker.factory == spotify_factory
        assert checker.matcher == matcher


class TestRemoteItemSearcherConfig:

    @pytest.fixture
    def model(self) -> RemoteItemSearcherConfig:
        return RemoteItemSearcherConfig()

    def test_create(self, model: RemoteItemCheckerConfig, matcher: ItemMatcher, spotify_factory: RemoteObjectFactory):
        searcher = model.create(factory=spotify_factory, matcher=matcher)

        assert searcher.factory == spotify_factory
        assert searcher.matcher == matcher


class TestRemoteItemDownloadConfig:

    @pytest.fixture
    def model(self) -> RemoteItemDownloadConfig:
        return RemoteItemDownloadConfig(
            urls=[
                "https://www.google.com/search?q={}",
                "https://www.youtube.com/results?search_query={}",
            ],
            fields=(TagFields.ARTIST, TagFields.ALBUM),
            interval=randrange(10, 20),
        )

    def test_create(self, model: RemoteItemDownloadConfig):
        downloader = model.create()

        assert downloader.urls == model.urls
        assert downloader.fields == list(model.fields)
        assert downloader.interval == model.interval


class TestRemoteNewMusicConfig:

    library_mock: type[RemoteLibraryMock] = SpotifyLibraryMock
    track_mock: type[RemoteTrackMock] = SpotifyTrackMock
    album_mock: type[RemoteAlbumMock] = SpotifyAlbumMock
    artist_mock: type[RemoteArtistMock] = SpotifyArtistMock

    @pytest.fixture
    def model(self, albums: list[RemoteAlbumMock]) -> RemoteNewMusicConfig:
        albums = sorted((album for album in albums if album.date), key=lambda alb: alb.date)
        start = albums[len(albums) // 3].date
        end = albums[2 * (len(albums) // 3)].date

        return RemoteNewMusicConfig(name="Super Cool New Music Playlist", start=start, end=end)

    @pytest.fixture
    def library(self) -> RemoteLibraryMock:
        library = self.library_mock()

        library.artists.extend([self.artist_mock({}) for _ in range(10)])
        for _ in range(100):
            artist = choice(library.artists)
            albums = [self.album_mock({}) for _ in range(randrange(1, 5))]
            for album in albums:
                album.extend([self.track_mock({}) for _ in range(randrange(5, 10))])
            artist.extend(albums)

        return library

    @pytest.fixture
    def albums(self, library: RemoteLibraryMock) -> list[RemoteAlbumMock]:
        # noinspection PyTypeChecker
        return [album for artist in library.artists for album in artist.albums]

    @pytest.fixture
    def expected_albums(self, model: RemoteNewMusicConfig, albums: list[RemoteAlbumMock]) -> list[RemoteAlbumMock]:
        expected = [
            alb for alb in albums if alb.date is not None and model.start <= alb.date <= model.end
        ]
        expected.extend(
            alb for alb in albums
            if alb.month is not None and alb.day is None
            and model.start.month <= alb.month <= model.end.month
        )
        expected.extend(
            alb for alb in albums if alb.month is None and model.start.year <= alb.year <= model.end.year
        )

        return expected

    def test_filter_artist_albums_by_date(
            self,
            model: RemoteNewMusicConfig,
            library: RemoteLibraryMock,
            albums: list[RemoteAlbumMock],
            expected_albums: list[RemoteAlbumMock],
    ):
        assert 0 < len(expected_albums) < len(albums)
        assert len(model._filter_artist_albums_by_date(library)) == len(expected_albums)

    async def test_create_playlist(
            self,
            model: RemoteNewMusicConfig,
            library: RemoteLibraryMock,
            albums: list[RemoteAlbumMock],
            expected_albums: list[RemoteAlbumMock],
    ):
        dry_run = choice([True, False])
        # noinspection PyTestUnpassedFixture
        expected_tracks = [track for album in model._filter_artist_albums_by_date(library) for track in album]
        assert expected_tracks

        assert model.name not in library.playlists

        pl, result = await model.run(library=library, dry_run=dry_run)
        pl: RemotePlaylistMock
        assert pl.name == model.name
        assert len(pl.tracks) == len(expected_tracks)
        assert pl.sync_args["kind"] == "refresh"
        assert pl.sync_args["dry_run"] == dry_run


class TestAPIHandlerRetry:

    @staticmethod
    def get_model() -> APIHandlerRetry:
        return APIHandlerRetry(
            initial=randrange(0, 300) / 100,
            count=randrange(5, 20),
            factor=randrange(100, 300) / 100
        )

    @pytest.fixture
    def model(self) -> APIHandlerRetry:
        return self.get_model()

    def test_create(self, model: APIHandlerRetry):
        timer = model.create()

        assert timer.initial == model.initial
        assert timer.count == model.count
        assert timer.factor == model.factor


class TestAPIHandlerWait:

    @staticmethod
    def get_model() -> APIHandlerWait:
        return APIHandlerWait(
            initial=randrange(0, 300) / 100,
            final=randrange(300, 700) / 100,
            step=randrange(0, 300) / 100
        )

    @pytest.fixture
    def model(self) -> APIHandlerWait:
        return self.get_model()

    def test_create(self, model: APIHandlerWait):
        timer = model.create()

        assert timer.initial == model.initial
        assert timer.final == model.final
        assert timer.step == model.step


class TestAPICacheConfig:

    @staticmethod
    def get_model() -> APICacheConfig:
        return APICacheConfig(
            type=choice(list(CACHE_TYPES)),
            db=random_str(),
            expire_after="P30DT10H5M50S"
        )

    @pytest.fixture
    def model(self) -> APICacheConfig:
        return self.get_model()

    def test_create(self, model: APICacheConfig):
        cache = model.create()

        assert cache.type == model.type
        assert model.db in cache.cache_name
        assert cache.expire == model.expire_after

        if model.type in (cls.type for cls in local_caches):
            assert model.is_local
        else:
            assert not model.is_local


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


###########################################################################
## Spotify
###########################################################################
class TestSpotifyAPIConfig:

    @staticmethod
    def get_model() -> APIConfig:
        return SpotifyAPIConfig(
            client_id="<CLIENT ID>",
            client_secret="<CLIENT SECRET>",
            scope=["scope 1", "scope 2"],
            token_file_path="token.json",
            cache=TestAPICacheConfig.get_model(),
            handler=APIHandlerConfig(
                retry=TestAPIHandlerRetry.get_model(),
                wait=TestAPIHandlerWait.get_model(),
            ),
        )

    @pytest.fixture
    def model(self) -> APIConfig:
        return self.get_model()

    def test_create(self, model: SpotifyAPIConfig):
        api = model.create()

        assert api.handler.authoriser.response.file_path == model.token_file_path
        assert api.handler.retry_timer == model.handler.retry.create()
        assert api.handler.wait_timer == model.handler.wait.create()

    def test_create_fails_on_invalid_credentials(self, model: SpotifyAPIConfig):
        with pytest.raises(ValidationError):  # no client id set
            SpotifyAPIConfig(
                client_id="",
                client_secret="<CLIENT SECRET>",
            )

        with pytest.raises(ValidationError):  # no client secret set
            SpotifyAPIConfig(
                client_id="<CLIENT ID>",
                client_secret="",
            )


class TestSpotifyLibraryConfig:
    @pytest.fixture
    def model(self) -> SpotifyLibraryConfig:
        return SpotifyLibraryConfig(
            name="spotify",
            api=TestSpotifyAPIConfig.get_model(),
            playlists=RemotePlaylistsConfig(
                filter=["playlist 1", "playlist 2"]
            ),
        )

    def test_create(self, model: RemoteLibraryConfig):
        library = model.create()

        assert isinstance(library, SpotifyLibrary)
        assert library.api.handler.authoriser.response.file_path == model.api.token_file_path
        assert library.playlist_filter == model.playlists.filter
