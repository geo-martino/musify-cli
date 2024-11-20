import pytest
from musify.field import TagFields
from musify.libraries.local.track import LocalTrack

from musify_cli.exception import ParserError
from musify_cli.tagger.getter import TagGetter, PathGetter, GETTERS_MAP


class TestGetter:

    def test_getter_in_config_map(self):
        assert TagGetter in GETTERS_MAP.values()
        assert GETTERS_MAP[None] == TagGetter

    def test_get(self, track: LocalTrack):
        getter = TagGetter(TagFields.TITLE)
        assert getter.get(track) == track.title

        getter = TagGetter(TagFields.TRACK_NUMBER)
        assert getter.get(track) == track.track_number

        getter = TagGetter(TagFields.YEAR)
        assert getter.get(track) == track.year

    def test_from_dict(self):
        config = {"field": "name"}
        getter = TagGetter.from_dict(config)
        assert getter.field == TagFields.NAME

        config = {"field": "track_number"}
        getter = TagGetter.from_dict(config)
        assert getter.field == TagFields.TRACK_NUMBER

        config = {"field": "year"}
        getter = TagGetter.from_dict(config)
        assert getter.field == TagFields.YEAR


class TestPathGetter:

    def test_getter_in_config_map(self):
        assert PathGetter in GETTERS_MAP.values()
        assert GETTERS_MAP["path"] == PathGetter

    def test_init_fails(self):
        with pytest.raises(ParserError):
            PathGetter(-1)
        with pytest.raises(ParserError):
            PathGetter(-5)

    def test_from_dict_fails(self):
        with pytest.raises(ParserError):
            config = {"parent": -1}
            PathGetter.from_dict(config)
        with pytest.raises(ParserError):
            config = {"parent": -5}
            PathGetter.from_dict(config)

    def test_get(self, track: LocalTrack):
        getter = PathGetter()
        assert getter.get(track) == track.path.name

        getter = PathGetter(1)
        assert getter.get(track) == track.path.parent.name

        getter = PathGetter(2)
        assert getter.get(track) == track.path.parts[-3]

    def test_from_dict(self, track: LocalTrack):
        getter = PathGetter.from_dict({})
        assert getter.parent == 0

        getter = PathGetter.from_dict({"field": "path"})
        assert getter.parent == 0

        getter = PathGetter.from_dict({"parent": "1"})
        assert getter.parent == 1

        getter = PathGetter.from_dict({"parent": "2"})
        assert getter.parent == 2
