from abc import ABCMeta, abstractmethod
from random import sample, choice

import pytest
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField

from musify_cli.tagger.getter import TagGetter
from musify_cli.tagger.setter import SETTERS_MAP, Clear, GroupedValueSetter, Min, Max, Join, Incremental


class TestClear:
    def test_setter_in_config_map(self):
        assert Clear in SETTERS_MAP.values()
        assert SETTERS_MAP["clear"] == Clear

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

    def test_from_dict(self):
        fields = [LocalTrackField.TITLE, LocalTrackField.YEAR, LocalTrackField.ALBUM]
        for field in fields:
            setter = Clear.from_dict(field, {})
            assert setter.field == field


class GroupedValueSetterTester(metaclass=ABCMeta):

    @abstractmethod
    def setter(self) -> GroupedValueSetter:
        raise NotImplementedError

    @pytest.fixture
    def tracks_group(self, setter: GroupedValueSetter, track: LocalTrack, tracks: list[LocalTrack]) -> list[LocalTrack]:
        group = sample(tracks, k=len(tracks) // 2)
        for tr in group:
            for field in setter.group_by:
                tr[field] = track[field]

        return group

    @staticmethod
    def test_group_items(
            setter: GroupedValueSetter,
            track: LocalTrack,
            tracks: list[LocalTrack],
            tracks_group: list[LocalTrack],
    ):
        assert sorted(setter._group_items(track, tracks)) == sorted(tr[setter.field] for tr in tracks_group)

    def test_from_dict(self, setter: GroupedValueSetter):
        field = LocalTrackField.TRACK

        # check default values are assigned on missing config
        setter = setter.__class__.from_dict(field=field, config={})
        assert setter.value_of == field

        config = {
            "field": "track_total",
            "group": ["album", "artist", "disc"]
        }
        setter = setter.__class__.from_dict(field=field, config=config)

        assert setter.value_of == LocalTrackField.TRACK_TOTAL
        assert sorted(setter.group_by) == sorted([
            LocalTrackField.ALBUM, LocalTrackField.ARTIST, LocalTrackField.DISC_NUMBER, LocalTrackField.DISC_TOTAL
        ])

class TestMin(GroupedValueSetterTester):
    @pytest.fixture
    def setter(self) -> Min:
        fields = [LocalTrackField.ALBUM, LocalTrackField.DISC_NUMBER, LocalTrackField.TITLE]
        return Min(field=LocalTrackField.TRACK, group_by=fields)

    def test_setter_in_config_map(self):
        assert Min in SETTERS_MAP.values()
        assert SETTERS_MAP["min"] == Min

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

    def test_setter_in_config_map(self):
        assert Max in SETTERS_MAP.values()
        assert SETTERS_MAP["max"] == Max

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


class TestJoin:
    def test_setter_in_config_map(self):
        assert Join in SETTERS_MAP.values()
        assert SETTERS_MAP["join"] == Join

    def test_set(self, track: LocalTrack, tracks: list[LocalTrack]):
        group_fields = [
            LocalTrackField.ALBUM, LocalTrackField.TITLE, LocalTrackField.EXT
        ]
        getters = [TagGetter(field) for field in group_fields]
        sep = "-"
        setter = Join(field=LocalTrackField.ARTIST, fields=getters, separator=sep)

        setter.set(track, tracks)
        assert track.artist == sep.join(getter.get(track) for getter in getters)

    def test_from_dict(self):
        field = LocalTrackField.ALBUM

        # check default values are assigned on missing config
        setter = Join.from_dict(field=field, config={})
        assert not setter.fields

        group_fields = [choice(LocalTrackField.all()) for _ in range(3)]
        config = {
            "separator": " - ",
            "values": [{"field": field.name.lower()} for field in group_fields]
        }

        setter = Join.from_dict(field=field, config=config)
        assert setter.field == field
        assert all(getter.field in group_fields for getter in setter.fields)


class TestIncremental:
    def test_setter_in_config_map(self):
        assert Incremental in SETTERS_MAP.values()
        assert SETTERS_MAP["incremental"] == Incremental

    def test_set(self, track: LocalTrack, tracks: list[LocalTrack]):
        if track not in tracks:
            tracks.append(track)

        track.track_number = 999999  # make it an unreasonably large number
        original_track = track.track_number

        sort_fields = [
            LocalTrackField.ALBUM, LocalTrackField.DISC_NUMBER, LocalTrackField.FILENAME
        ]
        setter = Incremental(field=LocalTrackField.TRACK, sort_by=sort_fields, start=-2, increment=3)
        assert sorted(setter.sort_by.sort_fields.keys()) == sorted(sort_fields)

        setter.set(track, tracks.copy())
        assert track.track_number != original_track

        setter.sort_by.sort(tracks)
        assert track.track_number == -2 + (tracks.index(track) * 3)

    def test_from_dict(self):
        field = LocalTrackField.DISC_NUMBER

        # check default values are assigned on missing config
        setter = Incremental.from_dict(field=field, config={})
        assert list(setter.sort_by.sort_fields.keys()) == [field]
        assert setter.start == 1
        assert setter.increment == 1

        sort_fields = [
            LocalTrackField.ALBUM, LocalTrackField.TITLE, LocalTrackField.EXT
        ]
        config = {
            "start": -5, "increment": -1, "sort": [field.name.lower() for field in sort_fields]
        }

        setter = setter.__class__.from_dict(field=field, config=config)
        assert sorted(setter.sort_by.sort_fields.keys()) == sorted(sort_fields)
        assert setter.start == -5
        assert setter.increment == -1


