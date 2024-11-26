from random import sample
from typing import Any

import pytest
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.filter import FilterDefinedList

from musify_cli.parser.operations.tagger import FilteredSetter, Tagger
# noinspection PyProtectedMember
from musify_cli.parser.operations.tagger._setter import Setter, Value
from tests.utils import random_tracks


class TestTagger:

    @pytest.fixture
    def values_expected(self) -> dict[str, Any]:
        return {
            "title": "title name",
            "artist": "artist name",
            "album": "album name",
        }

    @pytest.fixture
    def value_setters(self, values_expected: dict[str, Any]) -> list[Setter]:
        values_expected = {LocalTrackField.from_name(field)[0]: value for field, value in values_expected.items()}
        return [Value(field=field, value=value) for field, value in values_expected.items()]

    def test_set_values(self, value_setters: list[Setter], values_expected: dict[str, Any]):
        tracks = random_tracks(30)
        tracks_group = sample(tracks, k=15)
        for track in tracks_group:
            track.album = "i am an album name"

        filter_ = FilterDefinedList(values="i am an album name")
        filter_.transform = lambda tr: tr.album
        filtered_setter = FilteredSetter(filter=filter_, setters=value_setters)

        tagger = Tagger(setters=[filtered_setter])
        tagger.set_tags(tracks, ())

        for track in tracks:
            for field, value in values_expected.items():
                if track in tracks_group:
                    assert track[field] == value
                else:
                    assert track[field] != value