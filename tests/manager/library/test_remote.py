from datetime import datetime, timedelta
from abc import ABCMeta
from os.path import join
from pathlib import Path
from random import randrange, choice
from typing import Mapping, Iterable, Collection, Literal, Any

import pytest
from jsonargparse import Namespace
from musify.core.base import MusifyObject, MusifyItem
from musify.libraries.core.object import Library, Playlist
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.core.library import RemoteLibrary
from musify.libraries.remote.core.object import RemoteTrack, RemotePlaylist, RemoteAlbum, RemoteArtist
from musify.libraries.remote.core.object import SyncResultRemotePlaylist
from musify.libraries.remote.core.processors.check import RemoteItemChecker
from musify.libraries.remote.core.processors.search import RemoteItemSearcher
from musify.libraries.remote.core.processors.wrangle import RemoteDataWrangler
from musify.libraries.remote.spotify import SOURCE_NAME as SPOTIFY_SOURCE
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.libraries.remote.spotify.object import SpotifyTrack, SpotifyPlaylist, SpotifyAlbum, SpotifyArtist
from musify.processors.filter import FilterDefinedList, FilterIncludeExclude
from requests_cache import CachedSession

from musify_cli.exception import ParserError
from musify_cli.manager.library import RemoteLibraryManager, SpotifyLibraryManager
# noinspection PyProtectedMember
from musify_cli.parser._utils import get_comparers_filter, LoadTypesRemote, EnrichTypesRemote
from tests.manager.library.testers import LibraryManagerTester
from tests.utils import random_str


class RemoteLibraryManagerTester[T: RemoteLibraryManager](LibraryManagerTester, metaclass=ABCMeta):

    @pytest.fixture
    def load_types(self) -> type[LoadTypesRemote]:
        return LoadTypesRemote

    @pytest.fixture
    def manager_mock(self, manager: T) -> T:
        """
        Replace the instantiated library from the given ``manager`` with a mocked library.
        Yields the modified ``manager`` as a pytest.fixture.
        """
        manager._library = self.LibraryMock(
            api=manager.library.api,
            use_cache=manager.library.use_cache,
            playlist_filter=manager.library.playlist_filter
        )
        manager._library.factory.playlist = self.PlaylistMock
        manager._library.factory.playlist = self.AlbumMock
        return manager

    @staticmethod
    def test_init_factory(manager: T):
        assert manager._factory is None
        factory: RemoteObjectFactory = manager.factory
        assert factory.api.source == manager.source
        assert manager._factory is not None
        assert id(manager.factory) == id(manager._factory) == id(factory)

    @staticmethod
    def test_init_wrangler(manager: T):
        assert manager._wrangler is None
        wrangler: RemoteDataWrangler = manager.wrangler
        assert wrangler.source == manager.source
        assert manager._wrangler is not None
        assert id(manager.wrangler) == id(manager._wrangler) == id(wrangler)

    @staticmethod
    def test_init_check(manager: T, config: Namespace):
        checker: RemoteItemChecker = manager.check
        assert checker.interval == config.check.interval
        assert checker.allow_karaoke == config.check.allow_karaoke

        # always generates a new object when called twice
        config.check.interval += 100
        assert id(checker) != id(manager.check)
        assert manager.check.interval == config.check.interval

    @staticmethod
    def test_init_search(manager: T, config: Namespace):
        searcher: RemoteItemSearcher = manager.search
        assert searcher.use_cache == config.api.use_cache

        # always generates a new object when called twice
        config.api.use_cache = not config.api.use_cache
        assert id(searcher) != id(manager.search)
        assert manager.search.use_cache == config.api.use_cache

    ###########################################################################
    ## Operations
    ###########################################################################
    class LibraryMock(RemoteLibrary, metaclass=ABCMeta):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.load_calls: list[str] = []
            self.enrich_tracks_args: dict[str, Any] = {}
            self.enrich_saved_albums_args: dict[str, Any] = {}
            self.enrich_saved_artists_args: dict[str, Any] = {}
            self.sync_args: dict[str, Any] = {}

        def reset(self):
            """Reset all mock attributes"""
            self.load_calls.clear()
            self.enrich_tracks_args.clear()
            self.enrich_saved_albums_args.clear()
            self.enrich_saved_artists_args.clear()
            self.sync_args.clear()

        def load(self):
            self.load_calls.append("all")

        def load_tracks(self):
            self.load_calls.append("saved_tracks")

        def load_playlists(self):
            self.load_calls.append("playlists")

        def load_saved_albums(self):
            self.load_calls.append("saved_albums")

        def load_saved_artists(self):
            self.load_calls.append("saved_artists")

        def sync(
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
    def test_sync(manager_mock: T, config: Namespace, playlists: list[PlaylistMock]):
        manager_mock.dry_run = False

        include = FilterDefinedList([pl.name for pl in playlists][:3])
        include.transform = lambda value: value.name if isinstance(value, MusifyObject) else value
        manager_mock.config.playlists.filter = include

        manager_mock.sync(playlists)

        library_mock: RemoteLibraryManagerTester.LibraryMock = manager_mock.library
        assert len(library_mock.sync_args["playlists"]) == len(include.values)
        assert library_mock.sync_args["kind"] == config.playlists.sync.kind
        assert library_mock.sync_args["reload"] == config.playlists.sync.reload
        assert library_mock.sync_args["dry_run"] == manager_mock.dry_run

    @staticmethod
    @pytest.mark.skip(reason="Test not yet implemented")
    def test_get_or_create_playlist(manager_mock: T):
        pass  # TODO

    def test_filter_artist_albums_by_date(self, manager_mock: T):
        library: RemoteLibraryManagerTester.LibraryMock = manager_mock.library

        library.artists.extend(self.ArtistMock({}) for _ in range(10))

        for _ in range(100):
            artist: RemoteLibraryManagerTester.ArtistMock = choice(library.artists)
            artist._albums.append(self.AlbumMock({}))
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
    def config(self, tmp_path: Path) -> Namespace:
        return Namespace(
            api=Namespace(
                client_id="<CLIENT ID>",
                client_secret="<CLIENT SECRET>",
                scopes=[
                    "user-library-read",
                    "user-follow-read",
                ],
                token_path=join(tmp_path, "token.json"),
                cache_path=join(tmp_path, "cache"),
                use_cache=True,
            ),
            check=Namespace(
                interval=200,
                allow_karaoke=True,
            ),
            playlists=Namespace(
                filter=get_comparers_filter(["playlist 1", "playlist 2"]),
                sync=Namespace(
                    kind="sync",
                    reload=True,
                    filter={
                        "artist": ("bad artist", "nonce"),
                        "album": ("unliked album",),
                    },
                ),
            ),
        )

    @pytest.fixture
    def manager(self, config: Namespace) -> SpotifyLibraryManager:
        return SpotifyLibraryManager(name="spotify", config=config)

    def test_properties(self, manager: SpotifyLibraryManager, config: Namespace):
        assert manager.source == SPOTIFY_SOURCE
        assert manager.use_cache == config.api.use_cache

    def test_init_api_fails(self, manager: SpotifyLibraryManager):
        manager.config.api.client_id = None
        manager.config.api.client_secret = None
        with pytest.raises(ParserError):
            # noinspection PyStatementEffect
            manager.api

    def test_init_api(self, manager: SpotifyLibraryManager, config: Namespace):
        assert manager._api is None
        api: SpotifyAPI = manager.api
        assert manager._api is not None

        assert api.handler.token_file_path == config.api.token_path
        assert isinstance(api.handler.session, CachedSession)
        assert manager.use_cache

        # does not generate a new object when called twice even if config changes
        config.api.token_path = "/new/path/to/token.json"
        config.api.cache_path = "/new/path/to/cache"
        assert id(manager.api) == id(manager._api) == id(api)

    def test_init_library(self, manager: SpotifyLibraryManager, config: Namespace):
        assert manager._library is None
        library: SpotifyLibrary = manager.library
        assert manager._library is not None

        assert manager._api is not None
        assert id(library.api) == id(manager.api)
        assert library.use_cache == manager.use_cache
        assert library.playlist_filter == manager.playlist_filter == config.playlists.filter

        # does not generate a new object when called twice even if config changes
        config.playlists.filter = get_comparers_filter(["new playlist 1", "new playlist 2", "new playlist 3"])
        assert id(manager.library) == id(manager._library) == id(library)

    ###########################################################################
    ## Operations
    ###########################################################################
    class LibraryMock(RemoteLibraryManagerTester.LibraryMock, SpotifyLibrary):

        def enrich_tracks(
                self, features: bool = False, analysis: bool = False, albums: bool = False, artists: bool = False
        ) -> None:
            self.enrich_tracks_args = {
                "features": features, "analysis": analysis, "albums": albums, "artists": artists
            }

        def enrich_saved_albums(self) -> None:
            self.enrich_saved_albums_args = {}

        def enrich_saved_artists(self, tracks: bool = False, types: Collection[str] = ()) -> None:
            self.enrich_saved_artists_args = {"tracks": tracks, "types": types}

    class TrackMock(RemoteLibraryManagerTester.TrackMock, SpotifyTrack):
        pass

    class PlaylistMock(RemoteLibraryManagerTester.PlaylistMock, SpotifyPlaylist):
        pass

    class AlbumMock(RemoteLibraryManagerTester.AlbumMock, SpotifyAlbum):
        pass

    class ArtistMock(RemoteLibraryManagerTester.ArtistMock, SpotifyArtist):
        pass

    def test_enrich_all(self, manager_mock: SpotifyLibraryManager):
        library: TestSpotifyLibraryManager.LibraryMock = manager_mock.library

        manager_mock.types_loaded = set(LoadTypesRemote.all())

        assert LoadTypesRemote.saved_tracks not in manager_mock.types_enriched
        assert LoadTypesRemote.saved_albums not in manager_mock.types_enriched
        assert LoadTypesRemote.saved_artists not in manager_mock.types_enriched

        manager_mock.enrich()

        assert LoadTypesRemote.saved_tracks in manager_mock.types_enriched
        assert LoadTypesRemote.saved_albums in manager_mock.types_enriched
        assert LoadTypesRemote.saved_artists in manager_mock.types_enriched

        # just check each method was called
        assert library.enrich_tracks_args
        assert not library.enrich_saved_albums_args  # currently has no args
        assert library.enrich_saved_artists_args

        # should enrich all those that have been loaded only and skip those that have been enriched
        library.reset()
        manager_mock.enrich(force=True)

        assert LoadTypesRemote.saved_tracks in manager_mock.types_enriched
        assert LoadTypesRemote.saved_albums in manager_mock.types_enriched
        assert LoadTypesRemote.saved_artists in manager_mock.types_enriched

        # just check each method was called again
        assert library.enrich_tracks_args
        assert not library.enrich_saved_albums_args  # currently has no args
        assert library.enrich_saved_artists_args

    def test_enrich_limited_on_load_types(self, manager_mock: SpotifyLibraryManager):
        library: TestSpotifyLibraryManager.LibraryMock = manager_mock.library

        manager_mock.types_loaded = {LoadTypesRemote.saved_albums, LoadTypesRemote.saved_tracks}

        assert LoadTypesRemote.saved_tracks not in manager_mock.types_enriched
        assert LoadTypesRemote.saved_albums not in manager_mock.types_enriched
        assert LoadTypesRemote.saved_artists not in manager_mock.types_enriched

        manager_mock.enrich(types=LoadTypesRemote.saved_tracks)

        assert LoadTypesRemote.saved_tracks in manager_mock.types_enriched
        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.saved_tracks]
        assert enriched_types_track == {EnrichTypesRemote.artists, EnrichTypesRemote.albums}
        assert library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.saved_albums not in manager_mock.types_enriched
        assert LoadTypesRemote.saved_artists not in manager_mock.types_enriched

        # should enrich all those that have been loaded only and skip those that have been enriched
        library.reset()
        manager_mock.enrich()

        assert LoadTypesRemote.saved_tracks in manager_mock.types_enriched
        assert not library.enrich_tracks_args

        assert LoadTypesRemote.saved_albums in manager_mock.types_enriched
        enriched_types_album = manager_mock.types_enriched[LoadTypesRemote.saved_albums]
        assert not enriched_types_album
        assert not library.enrich_saved_albums_args  # currently has no args

        assert LoadTypesRemote.saved_artists not in manager_mock.types_enriched

        # on force, re-enriches loaded types but still doesn't try to enrich unloaded types
        library.reset()
        manager_mock.enrich(force=True)

        assert LoadTypesRemote.saved_tracks in manager_mock.types_enriched
        assert library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.saved_albums in manager_mock.types_enriched
        assert LoadTypesRemote.saved_artists not in manager_mock.types_enriched

    def test_enrich_limited_on_enrich_types(self, manager_mock: SpotifyLibraryManager):
        library: TestSpotifyLibraryManager.LibraryMock = manager_mock.library

        manager_mock.types_loaded = set(LoadTypesRemote.all())

        assert LoadTypesRemote.saved_tracks not in manager_mock.types_enriched
        assert LoadTypesRemote.saved_albums not in manager_mock.types_enriched
        assert LoadTypesRemote.saved_artists not in manager_mock.types_enriched

        manager_mock.enrich(enrich=EnrichTypesRemote.artists)

        assert LoadTypesRemote.saved_tracks in manager_mock.types_enriched
        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.saved_tracks]
        assert enriched_types_track == {EnrichTypesRemote.artists}
        assert not library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.saved_albums in manager_mock.types_enriched

        assert LoadTypesRemote.saved_artists in manager_mock.types_enriched
        enriched_types_artist = manager_mock.types_enriched[LoadTypesRemote.saved_artists]
        assert not enriched_types_artist
        assert not library.enrich_saved_artists_args["tracks"]

        # should skip those that have been enriched
        library.reset()
        manager_mock.enrich(enrich=EnrichTypesRemote.artists)

        assert not library.enrich_tracks_args
        assert not library.enrich_saved_artists_args

        # on force, re-enriches loaded types but still doesn't try to enrich unloaded types
        library.reset()
        manager_mock.enrich(enrich=EnrichTypesRemote.artists, force=True)

        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.saved_tracks]
        assert enriched_types_track == {EnrichTypesRemote.artists}
        assert not library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        enriched_types_artist = manager_mock.types_enriched[LoadTypesRemote.saved_artists]
        assert not enriched_types_artist
        assert not library.enrich_saved_artists_args["tracks"]
