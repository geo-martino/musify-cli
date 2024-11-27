import pytest
from musify.libraries.collection import BasicCollection
from musify.processors.filter import FilterComparers
from musify.utils import to_collection
from pydantic import TypeAdapter

from musify_cli.config.operations.filters import get_comparers_filter, Filter
from musify_cli.config.operations.signature import get_default_args


class TestFilter:
    @pytest.fixture
    def annotation(self) -> TypeAdapter:
        """The Pydantic annotation which is uses the function under test"""
        return TypeAdapter(Filter)

    @staticmethod
    def assert_filter_transform(filter_: Filter):
        """Checks the transform function always gives the MusifyObject's name"""
        obj = BasicCollection(name="collection name", items=[])
        assert filter_.transform(obj) == obj.name
        assert filter_.transform(obj.name) == obj.name

    def test_get_comparers_filter_string(self, annotation: TypeAdapter):
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

        assert filter_ == annotation.validate_python(config)

    def test_get_comparers_filter_collection(self, annotation: TypeAdapter):
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

        assert filter_ == annotation.validate_python(config)

    def test_get_comparers_filter_mapping(self, annotation: TypeAdapter):
        match_all = not get_default_args(FilterComparers)["match_all"]
        config = {
            "match_all": match_all,
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

        assert filter_ == annotation.validate_python(config | {"match_all": match_all})
