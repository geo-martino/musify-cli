from abc import ABCMeta, abstractmethod
from random import choice

import pytest
from musify.field import TagFields
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.compare import Comparer
from musify.processors.filter import FilterComparers

# noinspection PyProtectedMember
from musify_cli.config.operations.tagger._getter import GETTERS, getter_from_config, TagGetter, ConditionalGetter, \
    PathGetter
from musify_cli.exception import ParserError


def test_get_value_as_default_config():
    config = "track_number"
    getter = getter_from_config(config=config)
    assert isinstance(getter, TagGetter)
    assert getter.field == LocalTrackField.TRACK_NUMBER


class TagGetterTester(metaclass=ABCMeta):
    @abstractmethod
    def getter(self) -> TagGetter:
        raise NotImplementedError

    @staticmethod
    def test_adds_leading_zeros(getter: TagGetter, track: LocalTrack):
        # make the getter return a value which has a small width
        getter.field = LocalTrackField.TRACK_NUMBER

        getter.leading_zeros = 200
        result = getter.get(track)
        assert isinstance(result, str)
        assert result == result.zfill(getter.leading_zeros)

        getter.leading_zeros = LocalTrackField.TITLE
        result = getter.get(track)
        expected_width = len(str(track[getter.leading_zeros]))
        assert isinstance(result, str)
        assert result == result.zfill(expected_width)

    @staticmethod
    def test_from_field(getter: TagGetter):
        getter = getter.__class__.from_field("track_number")
        assert getter.field == LocalTrackField.TRACK_NUMBER


class TestTagGetter(TagGetterTester):

    @pytest.fixture
    def getter(self) -> TagGetter:
        return TagGetter(LocalTrackField.TRACK_NUMBER)

    def test_getter_from_config(self):
        assert TagGetter not in GETTERS
        config = {"field": "track_number"}
        getter = getter_from_config(config)
        assert isinstance(getter, TagGetter)

    # noinspection PyTestUnpassedFixture
    def test_from_dict(self):
        config = {"field": "name"}
        getter = TagGetter.from_dict(config)
        assert getter.field == TagFields.NAME
        assert getter.leading_zeros is None

        config = {"field": "track_number", "leading_zeros": "track_total"}
        getter = TagGetter.from_dict(config)
        assert getter.field == TagFields.TRACK_NUMBER
        assert getter.leading_zeros == TagFields.TRACK_TOTAL

        config = {"field": "year", "leading_zeros": 24}
        getter = TagGetter.from_dict(config)
        assert getter.field == TagFields.YEAR
        assert getter.leading_zeros == 24

    def test_get(self, track: LocalTrack):
        getter = TagGetter(TagFields.TITLE)
        assert getter.get(track) == track.title

        getter = TagGetter(TagFields.TRACK_NUMBER)
        assert getter.get(track) == track.track_number

        getter = TagGetter(TagFields.YEAR)
        assert getter.get(track) == track.year


class TestConditionalGetter(TagGetterTester):

    @pytest.fixture
    def getter(self) -> TagGetter:
        condition = FilterComparers()
        return ConditionalGetter(condition=condition, field=LocalTrackField.TRACK_NUMBER)

    def test_getter_from_config(self):
        assert ConditionalGetter not in GETTERS
        config = {"field": "track_number", "when": {}}
        getter = getter_from_config(config)
        assert isinstance(getter, ConditionalGetter)

    # noinspection PyTestUnpassedFixture
    def test_from_dict(self):
        config = {"field": "name"}
        getter = ConditionalGetter.from_dict(config)
        assert getter.field == TagFields.NAME
        assert not getter.condition.ready

        config = {"when": {"field": "track_number"}}
        getter = ConditionalGetter.from_dict(config)
        assert getter.field is None
        assert not getter.condition.ready

        config = {"field": "disc_number", "when": {"field": "track_number", "greater_than": 2}}
        getter = ConditionalGetter.from_dict(config)
        comparer = next(iter(getter.condition.comparers))
        assert getter.field == TagFields.DISC_NUMBER
        assert getter.condition.ready
        assert comparer.condition == "greater_than"
        assert comparer.field == TagFields.TRACK_NUMBER
        assert getter.condition.match_all

        config = {
            "value": "i am a value",
            "when": {
                "field": "year",
                "match_all": False,
                "is_in": ["this", "or", "that"]
            }
        }
        getter = ConditionalGetter.from_dict(config)
        comparer = next(iter(getter.condition.comparers))
        assert getter.field is None
        assert getter.condition.ready
        assert comparer.condition == "is_in"
        assert comparer.field == TagFields.YEAR
        assert not getter.condition.match_all

        # no field provided
        config = {
            "value": "i am a value",
            "when": {"is_in": ["this", "or", "that"]}
        }
        getter = ConditionalGetter.from_dict(config)
        assert getter.field is None
        assert getter.value == config["value"]

    def test_get_field(self, track: LocalTrack):
        comparer = Comparer(condition="is_in", expected=["this", "or", "that"], field=TagFields.TITLE)
        getter = ConditionalGetter(field=TagFields.ALBUM, condition=FilterComparers(comparer))
        assert track.title not in comparer.expected
        assert getter.get(track) is None
        track.title = choice(comparer.expected)
        assert getter.get(track) == track.album

        # field always takes priority
        getter.value = "---"
        assert getter.get(track) == track.album

    def test_get_value(self, track: LocalTrack):
        comparer = Comparer(condition="is_in", expected=["this", "or", "that"], field=TagFields.TITLE)
        getter = ConditionalGetter(
            value="---", condition=FilterComparers(comparers=comparer)
        )
        assert track.title not in comparer.expected
        assert getter.get(track) is None
        track.title = choice(comparer.expected)
        assert getter.get(track) == getter.value

        # field always takes priority
        getter.field = TagFields.ALBUM
        assert getter.get(track) == track.album


class TestPathGetter:

    def test_getter_from_config(self):
        assert PathGetter in GETTERS
        config = {"field": "path"}
        getter = getter_from_config(config)
        assert isinstance(getter, PathGetter)

    def test_from_dict_fails(self):
        with pytest.raises(ParserError):
            config = {"parent": -1}
            PathGetter.from_dict(config)
        with pytest.raises(ParserError):
            config = {"parent": -5}
            PathGetter.from_dict(config)

    def test_init_fails(self):
        with pytest.raises(ParserError):
            PathGetter(-1)
        with pytest.raises(ParserError):
            PathGetter(-5)

    def test_from_dict(self, track: LocalTrack):
        getter = PathGetter.from_dict({})
        assert getter.parent == 0

        getter = PathGetter.from_dict({"field": "path"})
        assert getter.parent == 0

        getter = PathGetter.from_dict({"parent": "1"})
        assert getter.parent == 1

        getter = PathGetter.from_dict({"parent": "2"})
        assert getter.parent == 2

    def test_get(self, track: LocalTrack):
        getter = PathGetter()
        assert getter.get(track) == track.path.name

        getter = PathGetter(1)
        assert getter.get(track) == track.path.parent.name

        getter = PathGetter(2)
        assert getter.get(track) == track.path.parts[-3]
