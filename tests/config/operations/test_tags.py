import pytest
from musify.field import TagFields
from musify.libraries.local.track.field import LocalTrackField
from musify.utils import to_collection
from pydantic import TypeAdapter

from musify_cli.exception import ParserError
from musify_cli.config.operations.tags import get_tags, TagFilter, LocalTrackFields, get_tag_filter


class TestTags:

    @pytest.fixture
    def annotation(self) -> TypeAdapter:
        """The Pydantic annotation which is uses the function under test"""
        return TypeAdapter(LocalTrackFields)

    @pytest.fixture
    def tag_fields(self) -> list[LocalTrackField]:
        """The tag fields to use in each test"""
        return [
            LocalTrackField.TITLE,
            LocalTrackField.ARTIST,
            LocalTrackField.ALBUM_ARTIST,
            LocalTrackField.BPM,
            LocalTrackField.COMPILATION,
        ]

    def test_fails_on_incorrect_field_types(self, tag_fields: list[LocalTrackField]):
        with pytest.raises(ParserError):
            get_tags(tag_fields, cls=TagFields)

    def test_input_is_tag_fields(self, tag_fields: list[LocalTrackField], annotation: TypeAdapter):
        expected = tuple(tag_fields)

        # always returns the input tags when they are already a collection of Fields
        results = get_tags(tag_fields, cls=LocalTrackField)
        assert results == expected
        assert annotation.validate_python(tag_fields) == expected

    def test_input_is_string(self, tag_fields: list[LocalTrackField], annotation: TypeAdapter):
        expected = tuple(TagFields.from_name(tag.name)[0] for tag in tag_fields)

        # gets tags by string
        tags = [tag.name.lower() for tag in tag_fields]
        results = get_tags(tags, cls=TagFields)
        assert all(tag.__class__ == TagFields for tag in results)
        assert results == expected
        assert annotation.validate_python(tags) == expected

    def test_input_is_all_fields(self, tag_fields: list[LocalTrackField], annotation: TypeAdapter):
        # gets all valid tags when given the ALL enum
        tags = [tag.name.lower() for tag in LocalTrackField.all()]
        expected = tuple(TagFields.from_name(tag)[0] for tag in tags if tag in LocalTrackField.__tags__)

        results = get_tags(LocalTrackField.ALL, cls=TagFields)
        assert all(tag.__class__ == TagFields for tag in results)
        assert results == expected
        assert annotation.validate_python(LocalTrackField.ALL) == expected


class TestTagFilter:
    @pytest.fixture
    def annotation(self) -> TypeAdapter:
        """The Pydantic annotation which is uses the function under test"""
        return TypeAdapter(TagFilter)

    def test_fails_on_invalid_fields(self):
        config = {
            "title": ["i am a track", "track name 2"],
            "artist": "artist name",
            "invalid_tag": "tag value",
        }

        with pytest.raises(ParserError, match="Unrecognised tag"):
            get_tag_filter(config)

    def test_fails_on_missing_tags(self):
        config = {
            "title": ["i am a track", "track name 2"],
            "artist": "artist name",
            "album": None,
        }

        with pytest.raises(ParserError, match="No value given"):
            get_tag_filter(config)

    def test_tag_filter(self, annotation: TypeAdapter):
        config = {
            "title": ["i am a track", "track name 2"],
            "artist": "artist name",
            "album": "album name",
            "track_number": [1, 2, 3]
        }

        result = get_tag_filter(config)

        for key, val in result.items():
            assert val == tuple(map(str, to_collection(config[key])))

        assert result == annotation.validate_python(config)
