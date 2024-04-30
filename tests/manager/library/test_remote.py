from abc import ABCMeta
from os.path import join
from pathlib import Path
from typing import Mapping, Iterable, Collection, Literal, Any

import pytest
from jsonargparse import Namespace
from musify.core.base import MusifyItem
from musify.libraries.core.object import Library, Playlist
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.core.library import RemoteLibrary
from musify.libraries.remote.core.object import RemotePlaylist, SyncResultRemotePlaylist
from musify.libraries.remote.core.processors.check import RemoteItemChecker
from musify.libraries.remote.core.processors.search import RemoteItemSearcher
from musify.libraries.remote.core.processors.wrangle import RemoteDataWrangler
from musify.libraries.remote.spotify import SOURCE_NAME as SPOTIFY_SOURCE
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.processors.filter import FilterDefinedList, FilterIncludeExclude
from requests_cache import CachedSession

from musify_cli.exception import ParserError
from musify_cli.manager.library import RemoteLibraryManager, SpotifyLibraryManager
# noinspection PyProtectedMember
from musify_cli.parser._utils import get_comparers_filter, LoadTypesRemote
from tests.manager.library.testers import LibraryManagerTester


class RemoteLibraryManagerTester[T: RemoteLibraryManager](LibraryManagerTester, metaclass=ABCMeta):

    @pytest.fixture
    def load_types(self) -> type[LoadTypesRemote]:
        return LoadTypesRemote

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

    def test_load_with_extend(self, manager_mock: T):
        pass  # TODO

    def test_load_with_enrich(self, manager_mock: T):
        pass  # TODO

    @staticmethod
    @pytest.mark.skip(reason="Need to enrich library with playlists for this to work")
    def test_filter_playlists_basic(manager_mock: T):
        include = FilterDefinedList([name for name in manager_mock.library.playlists][:1])
        manager_mock.config.playlists.filter = include
        playlists: dict[str, RemotePlaylist] = manager_mock.library.playlists

        pl_filtered = manager_mock._filter_playlists(playlists.values())
        assert len(pl_filtered) == len(include) < len(playlists)
        assert all(pl.name in include for pl in pl_filtered)

        exclude = FilterIncludeExclude(
            include=FilterDefinedList(),
            exclude=FilterDefinedList([name for name in playlists][:1])
        )
        manager_mock.config.playlists.filter = exclude
        pl_exclude = manager_mock._filter_playlists(playlists.values())
        assert len(pl_exclude) == len(playlists) - len(exclude.exclude.values) < len(playlists)
        assert all(pl.name not in exclude for pl in pl_exclude)

    @staticmethod
    @pytest.mark.skip(reason="Need to enrich library with playlists for this to work")
    def test_filter_playlists_on_tags(manager_mock: T):
        playlists: dict[str, RemotePlaylist] = manager_mock.library.playlists
        filter_names = [item.name for item in next(pl for pl in playlists.values() if len(pl) > 0)[:2]]
        manager_mock.config.playlists.sync.filter = {"name": [name.upper() + "  " for name in filter_names]}

        expected_counts = {}
        for name, pl in playlists.items():
            count_remaining = len([item for item in pl if item.name not in filter_names])
            if count_remaining < len(pl):
                expected_counts[name] = count_remaining

        if len(expected_counts) == 0:
            raise Exception("Can't check filter_tags logic, no items to filter out from playlists")

        filtered_playlists = manager_mock._filter_playlists(playlists.values())
        for pl in filtered_playlists:
            if pl.name not in expected_counts:
                continue
            assert len(pl) == expected_counts[pl.name]

    @staticmethod
    def test_sync(manager_mock: T, config: Namespace):
        manager_mock.dry_run = False

        playlists = []  # TODO: add some mock playlists here
        manager_mock.sync(playlists)

        library_mock: TestSpotifyLibraryManager.LibraryMock = manager_mock.library
        assert library_mock.sync_args["playlists"] == playlists
        assert library_mock.sync_args["kind"] == config.playlists.sync.kind
        assert library_mock.sync_args["reload"] == config.playlists.sync.reload
        assert library_mock.sync_args["dry_run"] == manager_mock.dry_run

    @staticmethod
    def test_get_playlist(manager_mock: T):
        pass  # TODO

    @staticmethod
    def test_filter_artist_albums_by_date(manager_mock: T):
        pass  # TODO


class TestSpotifyLibraryManager[T: RemoteLibraryManager](RemoteLibraryManagerTester):
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
    def manager(self, config: Namespace) -> T:
        return SpotifyLibraryManager(name="spotify", config=config)

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
        return manager

    def test_properties(self, manager: T, config: Namespace):
        assert manager.source == SPOTIFY_SOURCE
        assert manager.use_cache == config.api.use_cache

    def test_init_api_fails(self, manager: T):
        manager.config.api.client_id = None
        manager.config.api.client_secret = None
        with pytest.raises(ParserError):
            # noinspection PyStatementEffect
            manager.api

    def test_init_api(self, manager: T, config: Namespace):
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

    def test_init_library(self, manager: T, config: Namespace):
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
    class LibraryMock(SpotifyLibrary, RemoteLibraryManagerTester.LibraryMock):

        def enrich_tracks(
                self, features: bool = False, analysis: bool = False, albums: bool = False, artists: bool = False
        ) -> None:
            self.enrich_saved_artists_args = {
                "features": features, "analysis": analysis, "albums": albums, "artists": artists
            }

        def enrich_saved_albums(self) -> None:
            self.enrich_saved_albums_args = {}

        def enrich_saved_artists(self, tracks: bool = False, types: Collection[str] = ()) -> None:
            self.enrich_saved_artists_args = {"tracks": tracks, "types": types}

    def test_load_enrich(self, manager_mock: T):
        pass  # TODO
