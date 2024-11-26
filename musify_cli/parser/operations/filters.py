from typing import Mapping, TypeVar, Annotated

from aiorequestful.types import UnitSequence
from musify.base import MusifyObject
from musify.field import Fields
from musify.processors.compare import Comparer
from musify.processors.filter import FilterComparers
from pydantic import GetPydanticSchema
from pydantic_core import core_schema

from musify_cli.parser.operations.signature import get_default_args

UT = TypeVar("UT")
MultiType = UnitSequence[UT] | Mapping[str, UnitSequence[UT]]


def get_comparers_filter[T](config: MultiType[T]) -> FilterComparers[T | MusifyObject]:
    """Generate the :py:class:`FilterComparers` object from the ``config``"""
    match_all = get_default_args(FilterComparers)["match_all"]

    if isinstance(config, Mapping):
        field_str = config.get("field")
        field = next(iter(Fields.from_name(field_str))) if field_str is not None else None
        comparers = [
            Comparer(condition=cond, expected=exp, field=field) for cond, exp in config.items()
            if cond not in ["field", "match_all"]
        ]
        match_all = config.get("match_all", match_all)
    elif isinstance(config, str):
        comparers = Comparer(condition="is", expected=config)
    else:
        comparers = Comparer(condition="is in", expected=config)

    filter_ = FilterComparers(comparers=comparers, match_all=match_all)
    filter_.transform = lambda value: value.name if isinstance(value, MusifyObject) else value
    return filter_


Filter = Annotated[
    FilterComparers,
    GetPydanticSchema(
        lambda tp, handler: core_schema.no_info_before_validator_function(get_comparers_filter, handler(MultiType[str] | object))
    ),
]
