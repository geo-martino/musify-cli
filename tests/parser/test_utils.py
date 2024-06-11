import pytest
from musify.field import TagFields
from musify.libraries.collection import BasicCollection
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.base import Filter
from musify.processors.filter import FilterComparers
from musify.utils import to_collection

from musify_cli.exception import ParserError
from musify_cli.parser import CORE_PARSER
# noinspection PyProtectedMember
from musify_cli.parser._library import LIBRARY_EPILOG
# noinspection PyProtectedMember
from musify_cli.parser._utils import get_default_args, get_tags, get_comparers_filter


def test_epilog_formatter():
    assert CORE_PARSER.format_help().rstrip().endswith(LIBRARY_EPILOG.rstrip())


class TestParserTypes:

    def _test_function_for_default_args_1(self, arg1, arg2: str, arg3: int, arg4):
        pass

    def _test_function_for_default_args_2(self, arg1, arg2: str, arg3: int = 3, arg4="4"):
        pass

    def test_get_default_args(self):
        defaults = get_default_args(self.test_get_default_args)
        assert defaults == {}

        defaults = get_default_args(self._test_function_for_default_args_1)
        assert defaults == {}

        defaults = get_default_args(self._test_function_for_default_args_2)
        assert defaults == {"arg3": 3, "arg4": "4"}

    def test_get_tags(self):
        tag_fields = [
            LocalTrackField.TITLE,
            LocalTrackField.ARTIST,
            LocalTrackField.ALBUM_ARTIST,
            LocalTrackField.BPM,
            LocalTrackField.COMPILATION,
        ]
        with pytest.raises(ParserError):
            get_tags(tag_fields, cls=TagFields)

        # always returns the input tags when they are already a collection of Fields
        results = get_tags(tag_fields, cls=LocalTrackField)
        assert results == tuple(tag_fields)

        # gets tags by string
        results = get_tags([tag.name.lower() for tag in tag_fields], TagFields)
        assert all(tag.__class__ == TagFields for tag in results)
        assert results == tuple(TagFields.from_name(tag.name)[0] for tag in tag_fields)

        # gets all valid tags when given the ALL enum
        tags = [tag.name.lower() for tag in LocalTrackField.all()]
        results = get_tags(LocalTrackField.ALL, TagFields)
        assert all(tag.__class__ == TagFields for tag in results)
        assert results == tuple(TagFields.from_name(tag)[0] for tag in tags if tag in LocalTrackField.__tags__)

    @staticmethod
    def assert_filter_transform(filter_: Filter):
        """Checks the transform function always gives the MusifyObject's name"""
        obj = BasicCollection(name="collection name", items=[])
        assert filter_.transform(obj) == obj.name
        assert filter_.transform(obj.name) == obj.name

    def test_get_comparers_filter_string(self):
        config = "test_value"
        match_all = get_default_args(FilterComparers)["match_all"]
        filter_ = get_comparers_filter(config)

        assert filter_.match_all == match_all
        self.assert_filter_transform(filter_)

        assert len(filter_.comparers) == 1
        comparer, (combine, sub_filter) = next(iter(filter_.comparers.items()))
        assert comparer.condition == "is"
        assert comparer.expected == [config]
        assert not combine
        assert not sub_filter.ready

    def test_get_comparers_filter_collection(self):
        config = ["test_value_1", "test_value_2"]
        match_all = get_default_args(FilterComparers)["match_all"]
        filter_ = get_comparers_filter(config)

        assert filter_.match_all == match_all
        self.assert_filter_transform(filter_)

        assert len(filter_.comparers) == 1
        comparer, (combine, sub_filter) = next(iter(filter_.comparers.items()))
        assert comparer.condition == "is_in"
        assert comparer.expected == config
        assert not combine
        assert not sub_filter.ready

    def test_get_comparers_filter_mapping(self):
        config = {
            "match_all": not get_default_args(FilterComparers)["match_all"],
            "contains": "value 1",
            "in range": [20, 40],
            "starts with": "prefix",
        }
        filter_ = get_comparers_filter(config)

        assert filter_.match_all == config.pop("match_all")
        self.assert_filter_transform(filter_)

        assert len(filter_.comparers) == len(config)
        iterator = zip(filter_.comparers.items(), config.items())
        for ((comparer, (combine, sub_filter)), (condition, expected)) in iterator:
            assert comparer.condition == condition.replace(" ", "_")
            assert comparer.expected == to_collection(expected, list)
            assert not combine
            assert not sub_filter.ready
