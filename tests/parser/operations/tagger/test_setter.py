from abc import ABCMeta, abstractmethod
from random import sample, choice

import pytest
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField

from musify_cli.exception import ParserError
# noinspection PyProtectedMember
from musify_cli.parser.operations.tagger._getter import TagGetter
# noinspection PyProtectedMember
from musify_cli.parser.operations.tagger._setter import SETTERS, setter_from_config, \
    Value, Clear, GroupedValueSetter, Min, Max, Join, Incremental, GroupedSetter, Template, Field


def test_value_as_config():
    config = True
    setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
    assert isinstance(setter, Value)
    assert setter.value == config


def test_unrecognised_config():
    config = {"operation": "i am an invalid operation"}
    with pytest.raises(ParserError):
        setter_from_config(field=LocalTrackField.TITLE, config=config)


class TestValue:
    def test_setter_from_config(self):
        assert Value not in SETTERS
        config = {"value": "i am a value"}
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Value)

    def test_from_dict(self):
        config = {"value": "i am a value"}
        setter = Value.from_dict(field=LocalTrackField.TITLE, config=config)
        assert setter.value == config["value"]

    def test_set(self, track: LocalTrack):
        setter = Value(field=LocalTrackField.TITLE, value="i am a value")
        assert track.title != setter.value
        setter.set(track, ())
        assert track.title == setter.value


class TestField:
    def test_setter_from_config(self):
        assert Field not in SETTERS
        config = {"field": "year"}
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Field)

    def test_from_dict(self):
        config = {"field": "disc_number"}
        setter = Field.from_dict(field=LocalTrackField.TITLE, config=config)
        assert setter.value_of == LocalTrackField.DISC_NUMBER

    def test_set(self, track: LocalTrack):
        setter = Field(field=LocalTrackField.TITLE, value_of=LocalTrackField.YEAR)
        assert track.title != track.year
        setter.set(track, ())
        assert track.title == track.year


class TestClear:
    def test_setter_from_config(self):
        assert Clear in SETTERS
        config = {"operation": "clear"}
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Clear)

    def test_from_dict(self):
        fields = [LocalTrackField.TITLE, LocalTrackField.YEAR, LocalTrackField.ALBUM]
        for field in fields:
            setter = Clear.from_dict(field, {"operation": "clear"})
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


class TestJoin:
    def test_setter_from_config(self):
        assert Join in SETTERS
        config = {"operation": "join"}
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Join)

    def test_from_dict(self):
        field = LocalTrackField.ALBUM

        # check default values are assigned on missing config
        setter = Join.from_dict(field=field, config={})
        assert not setter.fields

        # noinspection PyTypeChecker
        group_fields = [LocalTrackField.from_name(choice(list(LocalTrackField.__tags__)))[0] for _ in range(3)]
        config = {
            "operation": "join",
            "separator": " - ",
            "values": [{"field": field.name.lower()} for field in group_fields]
        }

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


class GroupedSetterTester(metaclass=ABCMeta):

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

    def test_setter_from_config(self):
        assert Incremental in SETTERS
        config = {"operation": "incremental"}
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Incremental)

    # noinspection PyTestUnpassedFixture
    def test_from_dict(self):
        field = LocalTrackField.DISC_NUMBER

        # check default values are assigned on missing config
        setter = Incremental.from_dict(field=field, config={})
        assert list(setter.sort_by.sort_fields.keys()) == [field]
        assert setter.start == 1
        assert setter.increment == 1

        group_fields = [LocalTrackField.ALBUM, LocalTrackField.TITLE, LocalTrackField.EXT]
        sort_fields = [LocalTrackField.ARTIST]
        config = {
            "start": -5,
            "increment": -1,
            "sort": [field.name.lower() for field in sort_fields],
            "group": [field.name.lower() for field in group_fields]
        }

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

    @staticmethod
    def test_from_dict(setter: GroupedValueSetter):
        field = LocalTrackField.TRACK

        # check default values are assigned on missing config
        setter = setter.__class__.from_dict(field=field, config={})
        assert setter.value_of == field

        group_fields = [LocalTrackField.ALBUM, LocalTrackField.ARTIST, LocalTrackField.DISC_NUMBER]
        config = {
            "field": "track_total",
            "group": [field.name.lower() for field in group_fields],
        }
        setter = setter.__class__.from_dict(field=field, config=config)

        assert setter.value_of == LocalTrackField.TRACK_TOTAL
        assert sorted(setter.group_by) == sorted(group_fields)


class TestMin(GroupedValueSetterTester):
    @pytest.fixture
    def setter(self) -> Min:
        fields = [LocalTrackField.ALBUM, LocalTrackField.DISC_NUMBER, LocalTrackField.TITLE]
        return Min(field=LocalTrackField.TRACK, group_by=fields)

    def test_setter_from_config(self):
        assert Min in SETTERS
        config = {"operation": "min"}
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
        fields = [LocalTrackField.ALBUM, LocalTrackField.DISC_NUMBER, LocalTrackField.TITLE]
        return Max(field=LocalTrackField.TRACK, group_by=fields)

    def test_setter_from_config(self):
        assert Max in SETTERS
        config = {"operation": "max"}
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


class TestTemplate:
    def test_setter_from_config(self):
        assert Template in SETTERS
        config = {"operation": "template", "template": "i am a template"}
        setter = setter_from_config(field=LocalTrackField.TITLE, config=config)
        assert isinstance(setter, Template)

    def test_init_fails(self):
        with pytest.raises(ParserError, match=": new_value$"):
            template = "{album} - {artist} + {new_value}"
            Template(field=LocalTrackField.TITLE, template=template, fields={})

    def test_from_dict(self):
        config = {
            "operation": "template",
            "template": "{album} - {artist} + {new_value}",
            "new_value": {"field": "track_number"},
        }
        setter = Template.from_dict(field=LocalTrackField.TITLE, config=config)
        assert setter._required_fields == {"album", "artist", "new_value"}

        config = {
            "operation": "template",
            "template": "{album} - {artist} + {new_value}",
            "new_value": {"field": "track_number"},
            "artist": {"field": "genres"},
        }
        setter = Template.from_dict(field=LocalTrackField.TITLE, config=config)
        assert setter._required_fields == {"album", "artist", "new_value"}

    def test_set(self, track: LocalTrack):
        template = "{album} - {artist} + {new_value}"
        fields = {"new_value": TagGetter(field=LocalTrackField.TRACK_NUMBER)}
        setter = Template(field=LocalTrackField.TITLE, template=template, fields=fields)

        setter.set(track, ())
        assert track.title == f"{track.album} - {track.artist} + {track.track_number}"
