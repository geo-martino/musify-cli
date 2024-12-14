from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Iterable, Mapping
from random import sample, choice
from typing import Any

import pytest
from musify.field import TagFields
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.compare import Comparer
from musify.processors.filter import FilterComparers, FilterDefinedList
from tests.utils import random_str

# noinspection PyProtectedMember
from musify_cli.config.operations.tagger._getter import TagGetter
# noinspection PyProtectedMember
from musify_cli.config.operations.tagger._setter import SETTERS, setter_from_config, \
    Value, Clear, GroupedValueSetter, Min, Max, Join, Incremental, GroupedSetter, Template, Field, Setter
from musify_cli.exception import ParserError


def test_set_value_as_default_config():
    config = True
    setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
    assert isinstance(setter, Value)
    assert setter.value == config


def test_unrecognised_config():
    config = {"operation": "i am an invalid operation"}
    with pytest.raises(ParserError):
        setter_from_config(field=LocalTrackField.TITLE, config=config)


class SetterTester(metaclass=ABCMeta):
    @abstractmethod
    def setter(self) -> Setter:
        raise NotImplementedError

    @abstractmethod
    def config(self, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    @pytest.fixture
    def conditional_track(self, track: LocalTrack) -> LocalTrack:
        return track

    @pytest.fixture
    def conditional_tracks(self, conditional_track: LocalTrack, tracks: list[LocalTrack], **kwargs) -> list[LocalTrack]:
        return tracks + [conditional_track]

    def test_condition_from_dict(self, setter: Setter, config: dict[str, Any]):
        config["when"] = {"field": "track_number", "greater_than": 2}
        setter = setter.from_dict(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter.condition, FilterComparers)

        comparer = next(iter(setter.condition.comparers))
        assert comparer.field == LocalTrackField.TRACK_NUMBER
        assert comparer.condition == "greater_than"
        assert comparer.expected == [2]

    def test_conditional_set_no_condition(
            self, setter: Setter, conditional_track: LocalTrack, conditional_tracks: list[LocalTrack]
    ):
        setter.condition = FilterDefinedList()
        original_value = conditional_track[setter.field]

        setter.set(conditional_track, conditional_tracks)
        assert conditional_track[setter.field] != original_value

    def test_conditional_set_valid_condition(
            self, setter: Setter, conditional_track: LocalTrack, conditional_tracks: list[LocalTrack]
    ):
        comparer = Comparer(condition="is_in", expected=["this", "or", "that"], field=TagFields.ARTIST)
        setter.condition = FilterComparers(comparer)
        conditional_track.artist = choice(comparer.expected)
        original_value = conditional_track[setter.field]

        setter.set(conditional_track, conditional_tracks)
        assert conditional_track[setter.field] != original_value

    def test_conditional_set_invalid_condition(
            self, setter: Setter, conditional_track: LocalTrack, conditional_tracks: list[LocalTrack]
    ):
        comparer = Comparer(condition="is_in", expected=["this", "or", "that"], field=TagFields.ARTIST)
        setter.condition = FilterComparers(comparer)
        conditional_track.artist = random_str(10, 15)
        original_value = conditional_track[setter.field]

        setter.set(conditional_track, conditional_tracks)
        assert conditional_track[setter.field] == original_value


class TestValue(SetterTester):
    @pytest.fixture
    def setter(self) -> Value:
        return Value(field=LocalTrackField.TITLE, value=random_str())

    @pytest.fixture
    def config(self) -> dict[str, Any]:
        return {"value": "i am a value"}

    def test_setter_from_config(self, config: dict[str, Any]):
        assert Value not in SETTERS
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Value)

    def test_from_dict(self, config: dict[str, Any]):
        setter = Value.from_dict(field=LocalTrackField.TITLE, config=config)
        assert setter.value == config["value"]

    def test_set(self, track: LocalTrack):
        setter = Value(field=LocalTrackField.TITLE, value="i am a value")
        assert track.title != setter.value
        setter.set(track, ())
        assert track.title == setter.value


class TestField(SetterTester):
    @pytest.fixture
    def setter(self) -> Field:
        return Field(field=LocalTrackField.TITLE, value_of=LocalTrackField.ARTIST)

    @pytest.fixture
    def config(self) -> dict[str, Any]:
        return {"field": "disc_number"}

    def test_setter_from_config(self, config: dict[str, Any]):
        assert Field not in SETTERS
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Field)

    def test_from_dict(self, config: dict[str, Any]):
        setter = Field.from_dict(field=LocalTrackField.TITLE, config=config)
        assert setter.value_of == LocalTrackField.DISC_NUMBER

    def test_set(self, track: LocalTrack):
        setter = Field(field=LocalTrackField.TITLE, value_of=LocalTrackField.YEAR)
        assert track.title != track.year
        setter.set(track, ())
        assert track.title == track.year


class TestClear(SetterTester):
    @pytest.fixture
    def setter(self) -> Clear:
        return Clear(field=LocalTrackField.TITLE)

    @pytest.fixture
    def config(self) -> dict[str, Any]:
        return {"operation": "clear"}

    def test_setter_from_config(self, config: dict[str, Any]):
        assert Clear in SETTERS
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Clear)

    def test_from_dict(self, config: dict[str, Any]):
        fields = [LocalTrackField.TITLE, LocalTrackField.YEAR, LocalTrackField.ALBUM]
        for field in fields:
            setter = Clear.from_dict(field, config)
            assert setter.field == field

    def test_set(self, track: LocalTrack):
        original_value = track.title
        Clear(LocalTrackField.TITLE).set(track, ())
        assert track.title != original_value

        original_value = track.year
        Clear(LocalTrackField.YEAR).set(track, ())
        assert track.year != original_value

        original_value = track.artist
        Clear(LocalTrackField.ARTIST).set(track, ())
        assert track.artist != original_value

        original_value = track.genres.copy()
        Clear(LocalTrackField.GENRES).set(track, ())
        assert track.genres != original_value


class TestJoin(SetterTester):
    @pytest.fixture
    def setter(self) -> Join:
        fields = [
            TagGetter(LocalTrackField.ALBUM),
            TagGetter(LocalTrackField.ARTIST)
        ]
        return Join(field=LocalTrackField.TITLE, fields=fields, separator=" - ")

    @pytest.fixture
    def group_fields(self) -> list[LocalTrackField]:
        # noinspection PyTypeChecker
        return [LocalTrackField.from_name(choice(list(LocalTrackField.__tags__)))[0] for _ in range(3)]

    @pytest.fixture
    def config(self, group_fields: list[LocalTrackField]) -> dict[str, Any]:
        return {
            "operation": "join",
            "separator": " - ",
            "values": [{"field": field.name.lower()} for field in group_fields]
        }

    def test_setter_from_config(self, config: dict[str, Any]):
        assert Join in SETTERS
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Join)

    def test_from_dict(self, config: dict[str, Any], group_fields: list[LocalTrackField]):
        field = LocalTrackField.ALBUM

        # check default values are assigned on missing config
        setter = Join.from_dict(field=field, config={})
        assert not setter.fields

        setter = Join.from_dict(field=field, config=config)
        assert setter.field == field
        assert all(getter.field in group_fields for getter in setter.fields)

    def test_set(self, track: LocalTrack, tracks: list[LocalTrack]):
        group_fields = [LocalTrackField.ALBUM, LocalTrackField.TITLE, LocalTrackField.EXT]
        getters = [TagGetter(field) for field in group_fields]
        sep = "-"
        setter = Join(field=LocalTrackField.ARTIST, fields=getters, separator=sep)

        setter.set(track, tracks)
        assert track.artist == sep.join(getter.get(track) for getter in getters)


class GroupedSetterTester(SetterTester, metaclass=ABCMeta):

    @abstractmethod
    def setter(self) -> GroupedSetter:
        raise NotImplementedError

    @pytest.fixture
    def tracks_group(self, setter: GroupedValueSetter, track: LocalTrack, tracks: list[LocalTrack]) -> list[LocalTrack]:
        group = sample(tracks, k=len(tracks) // 2)
        for tr in group:
            for field in setter.group_by:
                tr[field] = track[field]

        tracks.append(track)
        group.append(track)

        return group

    # noinspection PyMethodOverriding
    @pytest.fixture
    def conditional_tracks(
            self,
            conditional_track: LocalTrack,
            tracks: list[LocalTrack],
            setter: Setter,
            tracks_group: list[LocalTrack]
    ) -> list[LocalTrack]:
        conditional_track[setter.field] = sorted(tr[setter.field] for tr in tracks_group)[len(tracks_group) // 2]
        return tracks + [conditional_track]

    @staticmethod
    def test_group_items(
            setter: GroupedValueSetter,
            track: LocalTrack,
            tracks: list[LocalTrack],
            tracks_group: list[LocalTrack],
    ):
        result = sorted(setter._group_items(track, tracks), key=lambda tr: tr.path)
        assert result == sorted(tracks_group, key=lambda tr: tr.path)


class TestIncremental(GroupedSetterTester):
    @pytest.fixture
    def setter(self) -> Incremental:
        group_fields = [LocalTrackField.ALBUM, LocalTrackField.DISC_NUMBER, LocalTrackField.TITLE]
        sort_fields = [LocalTrackField.ARTIST]
        return Incremental(
            field=LocalTrackField.TRACK, group_by=group_fields, sort_by=sort_fields, start=-2, increment=3
        )

    @pytest.fixture
    def group_fields(self) -> list[LocalTrackField]:
        return [LocalTrackField.ALBUM, LocalTrackField.TITLE, LocalTrackField.EXT]

    @pytest.fixture
    def sort_fields(self) -> list[LocalTrackField]:
        return [LocalTrackField.ARTIST]

    @pytest.fixture
    def config(self, group_fields: list[LocalTrackField], sort_fields: list[LocalTrackField]) -> dict[str, Any]:
        return {
            "operation": "incremental",
            "start": -5,
            "increment": -1,
            "sort": [field.name.lower() for field in sort_fields],
            "group": [field.name.lower() for field in group_fields]
        }

    def test_setter_from_config(self, config: dict[str, Any]):
        assert Incremental in SETTERS
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Incremental)

    def test_from_dict(self, config: dict[str, Any], sort_fields: list[LocalTrackField]):
        field = LocalTrackField.DISC_NUMBER

        # check default values are assigned on missing config
        setter = Incremental.from_dict(field=field, config={})
        assert list(setter.sort_by.sort_fields.keys()) == [field]
        assert setter.start == 1
        assert setter.increment == 1

        setter = setter.__class__.from_dict(field=field, config=config)
        assert sorted(setter.sort_by.sort_fields.keys()) == sorted(sort_fields)
        assert setter.start == -5
        assert setter.increment == -1

    def test_set_no_group(self, setter: Incremental, track: LocalTrack, tracks: list[LocalTrack]):
        if track not in tracks:
            tracks.append(track)

        track.track_number = 999999  # make it an unreasonably large number
        original_track = track.track_number

        sort_fields = [LocalTrackField.ALBUM, LocalTrackField.DISC_NUMBER, LocalTrackField.FILENAME]
        setter = Incremental(field=LocalTrackField.TRACK, sort_by=sort_fields, start=-2, increment=3)
        assert sorted(setter.sort_by.sort_fields.keys()) == sorted(sort_fields)

        setter.set(track, tracks)
        assert track.track_number != original_track

        setter.sort_by.sort(tracks)
        assert track.track_number == -2 + (tracks.index(track) * 3)

    def test_set_with_group(
            self,
            setter: Incremental,
            track: LocalTrack,
            tracks: list[LocalTrack],
            tracks_group: list[LocalTrack],
    ):
        setter.set(track, tracks)
        setter.sort_by.sort(tracks_group)
        assert track.track_number == -2 + (tracks_group.index(track) * 3)


class GroupedValueSetterTester(GroupedSetterTester, metaclass=ABCMeta):

    @pytest.fixture
    def group_fields(self) -> list[LocalTrackField]:
        return [LocalTrackField.ALBUM, LocalTrackField.ARTIST, LocalTrackField.DISC_NUMBER]

    @pytest.fixture
    def config(self, group_fields: list[LocalTrackField]) -> dict[str, Any]:
        return {
            "field": "track_total",
            "group": [field.name.lower() for field in group_fields],
        }

    @staticmethod
    def test_from_dict(setter: GroupedValueSetter, config: dict[str, Any], group_fields: list[LocalTrackField]):
        field = LocalTrackField.TRACK

        # check default values are assigned on missing config
        setter = setter.__class__.from_dict(field=field, config={})
        assert setter.value_of == field

        setter = setter.__class__.from_dict(field=field, config=config)

        assert setter.value_of == LocalTrackField.TRACK_TOTAL
        assert sorted(setter.group_by) == sorted(group_fields)

    @staticmethod
    def test_no_values(setter: GroupedValueSetter, track: LocalTrack, tracks: list[LocalTrack]):
        for track in tracks:
            track[setter.field] = None

        value = track[setter.field]
        setter.set(track, tracks)
        assert track[setter.field] == value


class TestMin(GroupedValueSetterTester):
    @pytest.fixture
    def setter(self) -> Min:
        fields = [LocalTrackField.ALBUM, LocalTrackField.DISC_NUMBER]
        return Min(field=LocalTrackField.TRACK, group_by=fields)

    def test_setter_from_config(self, config: dict[str, Any]):
        assert Min in SETTERS
        config["operation"] = "min"
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Min)

    def test_set_no_group(self, track: LocalTrack, tracks: list[LocalTrack]):
        setter = Min(field=LocalTrackField.TRACK)
        setter.set(track, tracks)
        assert track.track_number == min(tr.track_number for tr in tracks)

    def test_set_with_group(
            self,
            setter: GroupedValueSetter,
            track: LocalTrack,
            tracks: list[LocalTrack],
            tracks_group: list[LocalTrack],
    ):
        setter.set(track, tracks)
        assert track.track_number == min(tr.track_number for tr in tracks_group)

    def test_set_with_group_on_value(
            self,
            setter: GroupedValueSetter,
            track: LocalTrack,
            tracks: list[LocalTrack],
            tracks_group: list[LocalTrack],
    ):
        setter.value_of = LocalTrackField.ALBUM
        setter.set(track, tracks)
        assert track.album == min(tr.album for tr in tracks_group)


class TestMax(GroupedValueSetterTester):
    @pytest.fixture
    def setter(self) -> Max:
        fields = [LocalTrackField.ALBUM, LocalTrackField.DISC_NUMBER]
        return Max(field=LocalTrackField.TRACK, group_by=fields)

    def test_setter_from_config(self, config: dict[str, Any]):
        assert Max in SETTERS
        config["operation"] = "max"
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Max)

    def test_set_no_group(self, track: LocalTrack, tracks: list[LocalTrack]):
        setter = Max(field=LocalTrackField.TRACK)
        setter.set(track, tracks)
        assert track.track_number == max(tr.track_number for tr in tracks)

    def test_set_with_group(
            self,
            setter: GroupedValueSetter,
            track: LocalTrack,
            tracks: list[LocalTrack],
            tracks_group: list[LocalTrack],
    ):
        setter.set(track, tracks)
        assert track.track_number == max(tr.track_number for tr in tracks_group)

    def test_set_with_group_on_value(
            self,
            setter: GroupedValueSetter,
            track: LocalTrack,
            tracks: list[LocalTrack],
            tracks_group: list[LocalTrack],
    ):
        setter.value_of = LocalTrackField.ALBUM
        setter.set(track, tracks)
        assert track.album == max(tr.album for tr in tracks_group)


class TestTemplate(SetterTester):
    @pytest.fixture
    def setter(self) -> Template:
        return Template(field=LocalTrackField.ALBUM, template="{album} - {artist}")

    @pytest.fixture
    def config(self) -> dict[str, Any]:
        return {
            "operation": "template",
            "template": "{album} - {artist} + {new_value}",
            "new_value": {"field": "track_number"},
        }

    def test_setter_from_config(self, config: dict[str, Any]):
        assert Template in SETTERS
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Template)

    def test_init_fails(self):
        with pytest.raises(ParserError, match=": new_value$"):
            template = "{album} - {artist} + {new_value}"
            Template(field=LocalTrackField.TITLE, template=template, fields={})

    def test_from_dict(self, config: dict[str, Any]):
        setter = Template.from_dict(field=LocalTrackField.TITLE, config=config)
        assert setter._required_fields == {"album", "artist", "new_value"}

        config["artist"] = {"field": "genres"}
        setter = Template.from_dict(field=LocalTrackField.TITLE, config=config)
        assert setter._required_fields == {"album", "artist", "new_value"}
        assert setter.fields["artist"].field == LocalTrackField.GENRES

    def test_set(self, track: LocalTrack):
        template = "{album} - {artist} + {new_value}"
        fields = {"new_value": TagGetter(field=LocalTrackField.TRACK_NUMBER)}
        setter = Template(field=LocalTrackField.TITLE, template=template, fields=fields)

        setter.set(track, ())
        assert track.title == f"{track.album} - {track.artist} + {track.track_number}"
