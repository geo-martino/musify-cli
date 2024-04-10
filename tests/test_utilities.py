from copy import deepcopy

import pytest
from musify.libraries.core.object import Library
from musify.processors.filter import FilterDefinedList, FilterIncludeExclude

from musify_cli.main import Musify


@pytest.mark.skip(reason="Musify fixture not yet implemented")
class TestUtilities:

    @pytest.fixture(scope="class")
    def _library(self) -> Library:
        """Yields a loaded :py:class:`Library` object to be tested as pytest.fixture"""
        raise NotImplementedError

    @pytest.fixture
    def library(self, _library: Library) -> Library:
        """Yields a loaded :py:class:`Library` object to be tested as pytest.fixture"""
        return deepcopy(_library)

    def test_get_filtered_playlists_basic(self, main: Musify, library: Library):
        include = FilterDefinedList([name for name in library.playlists][:1])
        pl_include = main.filter_playlists(library.playlists.values(), playlist_filter=include)
        assert len(pl_include) == len(include) < len(library.playlists)
        assert all(pl.name in include for pl in pl_include)

        exclude = FilterIncludeExclude(
            include=FilterDefinedList(),
            exclude=FilterDefinedList([name for name in library.playlists][:1])
        )
        pl_exclude = main.filter_playlists(library.playlists.values(), playlist_filter=exclude)
        assert len(pl_exclude) == len(library.playlists) - len(exclude.exclude.values) < len(library.playlists)
        assert all(pl.name not in exclude for pl in pl_exclude)

    def test_get_filtered_playlists_on_tags(self, main: Musify, library: Library):
        # filters out tags
        filter_names = [item.name for item in next(pl for pl in library.playlists.values() if len(pl) > 0)[:2]]
        filter_tags = {"name": [name.upper() + "  " for name in filter_names]}
        expected_counts = {}
        for name, pl in library.playlists.items():
            count_remaining = len([item for item in pl if item.name not in filter_names])
            if count_remaining < len(pl):
                expected_counts[name] = count_remaining

        if len(expected_counts) == 0:
            raise Exception("Can't check filter_tags logic, no items to filter out from playlists")

        filtered_playlists = main.filter_playlists(library.playlists.values(), **filter_tags)
        for pl in filtered_playlists:
            if pl.name not in expected_counts:
                continue
            assert len(pl) == expected_counts[pl.name]
