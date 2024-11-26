from abc import ABCMeta
from collections.abc import Mapping, Iterable, Collection
from datetime import datetime, timedelta
from pathlib import Path
from random import randrange, choice
from typing import Literal, Any

import pytest
from musify.base import MusifyObject, MusifyItem
from musify.field import TagFields
from musify.libraries.core.object import Library, Playlist
from musify.libraries.remote.core.library import RemoteLibrary
from musify.libraries.remote.core.object import RemoteTrack, RemotePlaylist, RemoteAlbum, RemoteArtist
from musify.libraries.remote.core.object import SyncResultRemotePlaylist
from musify.libraries.remote.spotify import SOURCE_NAME as SPOTIFY_SOURCE
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.libraries.remote.spotify.object import SpotifyTrack, SpotifyPlaylist, SpotifyAlbum, SpotifyArtist
from musify.processors.filter import FilterDefinedList, FilterIncludeExclude

from musify_cli.exception import ParserError
from musify_cli.manager.library import RemoteLibraryManager, SpotifyLibraryManager
from musify_cli.parser.library import RemoteLibraryConfig, SpotifyAPIConfig, APICacheConfig, \
    APIHandlerConfig, APIHandlerRetry, APIHandlerWait, RemoteCheckerConfig, RemoteItemDownloadConfig, \
    RemotePlaylistsConfig, RemotePlaylistsSync
from musify_cli.parser.types import LoadTypesRemote, EnrichTypesRemote
from tests.manager.library.testers import LibraryManagerTester
from tests.utils import random_str


class RemoteLibraryManagerTester[T: RemoteLibraryManager](LibraryManagerTester, metaclass=ABCMeta):

    @pytest.fixture
    def load_types(self) -> type[LoadTypesRemote]:
        return LoadTypesRemote

    # noinspection PyProtectedMember
    @pytest.fixture
    async def manager_mock(self, manager: T) -> T:
        """
        Replace the instantiated library from the given ``manager`` with a mocked library.
        Yields the modified ``manager`` as a pytest.fixture.
        """
        manager._library_cls = self.LibraryMock
        manager.factory.playlist = self.PlaylistMock
        manager.factory.album = self.AlbumMock

        return manager

    ###########################################################################
    ## Operations
    ###########################################################################
    class LibraryMock(RemoteLibrary, metaclass=ABCMeta):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.load_calls: list[str] = []
            self.enrich_tracks_args: dict[str, Any] = {}
            self.enrich_SAVED_ALBUMS_args: dict[str, Any] = {}
            self.enrich_SAVED_ARTISTS_args: dict[str, Any] = {}
            self.sync_args: dict[str, Any] = {}

        def reset(self):
            """Reset all mock attributes"""
            self.load_calls.clear()
            self.enrich_tracks_args.clear()
            self.enrich_SAVED_ALBUMS_args.clear()
            self.enrich_SAVED_ARTISTS_args.clear()
            self.sync_args.clear()

        async def load(self):
            self.load_calls.append("ALL")

        async def load_tracks(self):
            self.load_calls.append(LoadTypesRemote.SAVED_TRACKS.name)

        async def load_playlists(self):
            self.load_calls.append(LoadTypesRemote.PLAYLISTS.name)

        async def load_saved_albums(self):
            self.load_calls.append(LoadTypesRemote.SAVED_ALBUMS.name)

        async def load_saved_artists(self):
            self.load_calls.append(LoadTypesRemote.SAVED_ARTISTS.name)

        async def sync(
                self,
                playlists: Library | Mapping[str, Iterable[MusifyItem]] | Collection[Playlist] | None = None,
                kind: Literal["new", "refresh", "sync"] = "new",
                reload: bool = True,
                dry_run: bool = True
        ) -> dict[str, SyncResultRemotePlaylist]:
            self.sync_args = {"playlists": playlists, "kind": kind, "reload": reload, "dry_run": dry_run}
            return {}

    class TrackMock(RemoteTrack, metaclass=ABCMeta):
        def __init__(self, *args, **kwargs):
            kwargs.pop("skip_checks", None)
            super().__init__(*args, **kwargs, skip_checks=True)

            self._name = random_str()

        def _check_type(self) -> None:
            pass

        @property
        def name(self):
            return self._name

        @property
        def uri(self):
            return self._name

    class PlaylistMock(RemotePlaylist, metaclass=ABCMeta):
        def __init__(self, *args, **kwargs):
            kwargs.pop("skip_checks", None)
            super().__init__(*args, **kwargs, skip_checks=True)

            self._name = random_str()

        def _check_type(self) -> None:
            pass

        @property
        def name(self):
            return self._name

        @property
        def uri(self):
            return self._name

    class AlbumMock(RemoteAlbum, metaclass=ABCMeta):
        def __init__(self, *args, **kwargs):
            kwargs.pop("skip_checks", None)
            super().__init__(*args, **kwargs, skip_checks=True)

            self._year = datetime.now().year
            self._month = choice([None, randrange(1, 12)])
            self._day = choice([None, randrange(1, 28)]) if self._month is not None else None
            if self._month is not None and self._day is not None:
                self._date = datetime(self._year, self._month, self._day)
            else:
                self._date = None

        def _check_type(self) -> None:
            pass

        @property
        def date(self):
            return self._date

        @property
        def year(self):
            return self._year

        @property
        def month(self):
            return self._month

        @property
        def day(self):
            return self._day

    class ArtistMock(RemoteArtist, metaclass=ABCMeta):
        def __init__(self, *args, **kwargs):
            kwargs.pop("skip_checks", None)
            super().__init__(*args, **kwargs, skip_checks=True)

        def _check_type(self) -> None:
            pass

    @pytest.fixture
    def playlists(self) -> list[PlaylistMock]:
        """Yields some mock :py:class:`RemotePlaylist` objects as a pytest.fixture."""
        playlists = [self.PlaylistMock({}) for _ in range(10)]
        for pl in playlists:
            pl.tracks.extend(self.TrackMock({}) for _ in range(50))
        return playlists

    @staticmethod
    def test_filter_playlists_basic(manager_mock: T, playlists: list[PlaylistMock]):
        include = FilterDefinedList([pl.name for pl in playlists][:3])
        include.transform = lambda value: value.name if isinstance(value, MusifyObject) else value
        manager_mock.config.playlists.filter = include

        pl_filtered = manager_mock._filter_playlists(playlists)
        assert len(pl_filtered) == len(include) < len(playlists)
        assert all(pl.name in include for pl in pl_filtered)

        exclude = FilterIncludeExclude(
            include=FilterDefinedList(),
            exclude=FilterDefinedList([pl.name for pl in playlists][:3])
        )
        exclude.transform = include.transform
        manager_mock.config.playlists.filter = exclude

        pl_exclude = manager_mock._filter_playlists(playlists)
        assert len(pl_exclude) == len(playlists) - len(exclude.exclude.values) < len(playlists)
        assert all(pl.name not in exclude for pl in pl_exclude)

    @staticmethod
    def test_filter_playlists_on_tags(manager_mock: T, playlists: list[PlaylistMock]):
        filter_names = [item.name for item in next(pl for pl in playlists if len(pl) > 0)[:2]]
        manager_mock.config.playlists.sync.filter = {"name": [name.upper() + "  " for name in filter_names]}

        expected_counts = {}
        for pl in playlists:
            count_remaining = len([item for item in pl if item.name not in filter_names])
            if count_remaining < len(pl):
                expected_counts[pl.name] = count_remaining

        if len(expected_counts) == 0:
            raise Exception("Can't check filter_tags logic, no items to filter out from playlists")

        filtered_playlists = manager_mock._filter_playlists(playlists)
        for pl in filtered_playlists:
            if pl.name not in expected_counts:
                continue
            assert len(pl) == expected_counts[pl.name]

    @staticmethod
    async def test_sync(manager_mock: T, config: RemoteLibraryConfig, playlists: list[PlaylistMock]):
        manager_mock.dry_run = False

        include = FilterDefinedList([pl.name for pl in playlists][:3])
        include.transform = lambda value: value.name if isinstance(value, MusifyObject) else value
        manager_mock.config.playlists.filter = include

        await manager_mock.sync(playlists)

        library_mock: RemoteLibraryManagerTester.LibraryMock = manager_mock.library
        assert len(library_mock.sync_args["playlists"]) == len(include.values)
        assert library_mock.sync_args["kind"] == config.playlists.sync.kind
        assert library_mock.sync_args["reload"] == config.playlists.sync.reload
        assert library_mock.sync_args["dry_run"] == manager_mock.dry_run

    def test_filter_artist_albums_by_date(self, manager_mock: T):
        library: RemoteLibraryManagerTester.LibraryMock = manager_mock.library

        library.artists.extend(self.ArtistMock({}) for _ in range(10))

        for _ in range(100):
            artist: RemoteLibraryManagerTester.ArtistMock = choice(library.artists)
            # noinspection PyTypeChecker
            artist.append(self.AlbumMock({}))
        albums = [album for artist in library.artists for album in artist.albums]

        end = datetime.now()
        start = end - timedelta(days=60)

        expected_counts = sum(
            1 for alb in albums if alb.date is not None and start <= alb.date <= end
        )
        expected_counts += sum(
            1 for alb in albums if alb.month is not None and alb.day is None and start.month <= alb.month <= end.month
        )
        expected_counts += sum(
            1 for alb in albums if alb.month is None and start.year <= alb.year <= end.year
        )

        assert 0 < expected_counts < len(albums)
        assert len(manager_mock.filter_artist_albums_by_date(start=start, end=end)) == expected_counts


class TestSpotifyLibraryManager(RemoteLibraryManagerTester[SpotifyLibraryManager]):
    @pytest.fixture
    def config(self, tmp_path: Path) -> RemoteLibraryConfig:
        return RemoteLibraryConfig(
            name="name",
            api=SpotifyAPIConfig(
                client_id="<CLIENT ID>",
                client_secret="<CLIENT SECRET>",
                scope=[
                    "user-library-read",
                    "user-follow-read",
                ],
                handler=APIHandlerConfig(
                    retry=APIHandlerRetry(
                        initial=2,
                        count=20,
                        factor=1.5,
                    ),
                    wait=APIHandlerWait(
                        initial=1,
                        final=3,
                        step=0.3,
                    ),
                ),
                cache=APICacheConfig(
                    type="sqlite",
                    db=str(tmp_path.joinpath("cache_db")),
                    expire_after=timedelta(days=16),
                ),
                token_file_path=tmp_path.joinpath("token.json"),
            ),
            check=RemoteCheckerConfig(
                interval=200,
                allow_karaoke=True,
            ),
            download=RemoteItemDownloadConfig(
                urls=[
                    "https://www.google.com/search?q={}",
                    "https://www.youtube.com/results?search_query={}",
                ],
                fields=(TagFields.ARTIST, TagFields.ALBUM),
                interval=4,
            ),
            playlists=RemotePlaylistsConfig(
                filter=["playlist 1", "playlist 2"],
                sync=RemotePlaylistsSync(
                    kind="sync",
                    reload=True,
                    filter={
                        "artist": ("bad artist", "nonce"),
                        "album": ("unliked album",),
                    },
                ),
            ),
        )

    # noinspection PyMethodOverriding
    @pytest.fixture
    async def manager(self, config: RemoteLibraryConfig) -> SpotifyLibraryManager:
        manager = SpotifyLibraryManager(config=config)

        authoriser = manager.api.handler.authoriser
        authoriser.response.replace({
            "access_token": "fake access token", "token_type": "Bearer", "scope": "test-read"
        })
        authoriser.tester.request = None
        authoriser.tester.response_test = None
        authoriser.tester.max_expiry = 0

        async with manager as m:
            yield m

    def test_properties(self, manager: SpotifyLibraryManager, config: RemoteLibraryConfig):
        assert manager.source == SPOTIFY_SOURCE

    def test_init_api_fails(self, config: RemoteLibraryConfig):
        manager = SpotifyLibraryManager(config=config)
        config.api.client_id = None
        config.api.client_secret = None

        with pytest.raises(ParserError):
            # noinspection PyStatementEffect
            manager.api

    ###########################################################################
    ## Operations
    ###########################################################################
    class LibraryMock(RemoteLibraryManagerTester.LibraryMock, SpotifyLibrary):

        async def enrich_tracks(
                self, features: bool = False, analysis: bool = False, albums: bool = False, artists: bool = False
        ) -> None:
            self.enrich_tracks_args = {
                "features": features, "analysis": analysis, "albums": albums, "artists": artists
            }

        async def enrich_saved_albums(self) -> None:
            self.enrich_SAVED_ALBUMS_args = {}

        async def enrich_saved_artists(self, tracks: bool = False, types: Collection[str] = ()) -> None:
            self.enrich_SAVED_ARTISTS_args = {"tracks": tracks, "types": types}

    class TrackMock(RemoteLibraryManagerTester.TrackMock, SpotifyTrack):
        pass

    class PlaylistMock(RemoteLibraryManagerTester.PlaylistMock, SpotifyPlaylist):
        pass

    class AlbumMock(RemoteLibraryManagerTester.AlbumMock, SpotifyAlbum):
        pass

    class ArtistMock(RemoteLibraryManagerTester.ArtistMock, SpotifyArtist):
        pass

    async def test_enrich_all(self, manager_mock: SpotifyLibraryManager):
        # noinspection PyTypeChecker
        library: TestSpotifyLibraryManager.LibraryMock = manager_mock.library

        manager_mock.types_loaded = set(LoadTypesRemote.all())

        assert LoadTypesRemote.SAVED_TRACKS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        await manager_mock.enrich()

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS in manager_mock.types_enriched

        # just check each method was called
        assert library.enrich_tracks_args
        assert not library.enrich_SAVED_ALBUMS_args  # currently has no args
        assert library.enrich_SAVED_ARTISTS_args

        # should enrich all those that have been loaded only and skip those that have been enriched
        library.reset()
        await manager_mock.enrich(force=True)

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS in manager_mock.types_enriched

        # just check each method was called again
        assert library.enrich_tracks_args
        assert not library.enrich_SAVED_ALBUMS_args  # currently has no args
        assert library.enrich_SAVED_ARTISTS_args

    async def test_enrich_limited_on_load_types(self, manager_mock: SpotifyLibraryManager):
        # noinspection PyTypeChecker
        library: TestSpotifyLibraryManager.LibraryMock = manager_mock.library

        manager_mock.types_loaded = {LoadTypesRemote.SAVED_ALBUMS, LoadTypesRemote.SAVED_TRACKS}

        assert LoadTypesRemote.SAVED_TRACKS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        await manager_mock.enrich(types=LoadTypesRemote.SAVED_TRACKS)

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.SAVED_TRACKS]
        assert enriched_types_track == {EnrichTypesRemote.ARTISTS, EnrichTypesRemote.ALBUMS}
        assert library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.SAVED_ALBUMS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        # should enrich all those that have been loaded only and skip those that have been enriched
        library.reset()
        await manager_mock.enrich()

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        assert not library.enrich_tracks_args

        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched
        enriched_types_album = manager_mock.types_enriched[LoadTypesRemote.SAVED_ALBUMS]
        assert not enriched_types_album
        assert not library.enrich_SAVED_ALBUMS_args  # currently has no args

        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        # on force, re-enriches loaded types but still doesn't try to enrich unloaded types
        library.reset()
        await manager_mock.enrich(force=True)

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        assert library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

    async def test_enrich_limited_on_enrich_types(self, manager_mock: SpotifyLibraryManager):
        # noinspection PyTypeChecker
        library: TestSpotifyLibraryManager.LibraryMock = manager_mock.library

        manager_mock.types_loaded = set(LoadTypesRemote.all())

        assert LoadTypesRemote.SAVED_TRACKS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        await manager_mock.enrich(enrich=EnrichTypesRemote.ARTISTS)

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.SAVED_TRACKS]
        assert enriched_types_track == {EnrichTypesRemote.ARTISTS}
        assert not library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched

        assert LoadTypesRemote.SAVED_ARTISTS in manager_mock.types_enriched
        enriched_types_artist = manager_mock.types_enriched[LoadTypesRemote.SAVED_ARTISTS]
        assert not enriched_types_artist
        assert not library.enrich_SAVED_ARTISTS_args["tracks"]

        # should skip those that have been enriched
        library.reset()
        await manager_mock.enrich(enrich=EnrichTypesRemote.ARTISTS)

        assert not library.enrich_tracks_args
        assert not library.enrich_SAVED_ARTISTS_args

        # on force, re-enriches loaded types but still doesn't try to enrich unloaded types
        library.reset()
        await manager_mock.enrich(enrich=EnrichTypesRemote.ARTISTS, force=True)

        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.SAVED_TRACKS]
        assert enriched_types_track == {EnrichTypesRemote.ARTISTS}
        assert not library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        enriched_types_artist = manager_mock.types_enriched[LoadTypesRemote.SAVED_ARTISTS]
        assert not enriched_types_artist
        assert not library.enrich_SAVED_ARTISTS_args["tracks"]
