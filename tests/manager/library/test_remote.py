from abc import ABCMeta

import pytest
from jsonargparse import Namespace
from musify.libraries.remote.core.object import RemotePlaylist
from musify.libraries.remote.spotify import SOURCE_NAME as SPOTIFY_SOURCE
from musify.processors.filter import FilterDefinedList, FilterIncludeExclude

from musify_cli.manager.library import RemoteLibraryManager, SpotifyLibraryManager
from tests.manager.library.testers import LibraryManagerTester


class RemoteLibraryManagerTester[T: RemoteLibraryManager](LibraryManagerTester, metaclass=ABCMeta):
    pass


class TestSpotifyLibraryManager[T: RemoteLibraryManager](RemoteLibraryManagerTester):

    @pytest.fixture
    def manager(self) -> T:
        config = Namespace(

        )
        return SpotifyLibraryManager(name="spotify", config=config)

    def test_properties(self, manager: T):
        assert manager.source == SPOTIFY_SOURCE

    @pytest.mark.skip(reason="SpotifyLibraryManager fixture not yet implemented")
    def test_get_filtered_playlists_basic(self, manager: T):
        include = FilterDefinedList([name for name in manager.library.playlists][:1])
        manager.config.playlists.filter = include
        playlists: dict[str, RemotePlaylist] = manager.library.playlists

        pl_filtered = manager._filter_playlists(playlists.values())
        assert len(pl_filtered) == len(include) < len(playlists)
        assert all(pl.name in include for pl in pl_filtered)

        exclude = FilterIncludeExclude(
            include=FilterDefinedList(),
            exclude=FilterDefinedList([name for name in playlists][:1])
        )
        manager.config.playlists.filter = exclude
        pl_exclude = manager._filter_playlists(playlists.values())
        assert len(pl_exclude) == len(playlists) - len(exclude.exclude.values) < len(playlists)
        assert all(pl.name not in exclude for pl in pl_exclude)

    @pytest.mark.skip(reason="SpotifyLibraryManager fixture not yet implemented")
    def test_get_filtered_playlists_on_tags(self, manager: T):
        playlists: dict[str, RemotePlaylist] = manager.library.playlists
        filter_names = [item.name for item in next(pl for pl in playlists.values() if len(pl) > 0)[:2]]
        manager.config.playlists.sync.filter = {"name": [name.upper() + "  " for name in filter_names]}

        expected_counts = {}
        for name, pl in playlists.items():
            count_remaining = len([item for item in pl if item.name not in filter_names])
            if count_remaining < len(pl):
                expected_counts[name] = count_remaining

        if len(expected_counts) == 0:
            raise Exception("Can't check filter_tags logic, no items to filter out from playlists")

        filtered_playlists = manager._filter_playlists(playlists.values())
        for pl in filtered_playlists:
            if pl.name not in expected_counts:
                continue
            assert len(pl) == expected_counts[pl.name]
