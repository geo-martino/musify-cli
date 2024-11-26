from collections.abc import Mapping, Collection
from dataclasses import dataclass
from typing import Any, Self

from musify.base import MusifyItemSettable
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.base import Filter
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from musify_cli.parser.operations.filters import get_comparers_filter
from musify_cli.parser.operations.tagger._setter import Setter, setter_from_config


@dataclass
class FilteredSetter[T: MusifyItemSettable]:
    """Stores the settings to apply setters to a limited set of filtered items based on a configured filter."""
    filter: Filter[T]
    setters: Collection[Setter]

    def set_tags(self, item: T, collection: Collection[T]) -> None:
        """
        Apply setters on the given ``item`` from the given ``collection``.

        :param item: The item to set tags for.
        :param collection: The collection the given item belongs to.
        """
        for setter in self.setters:
            setter.set(item, collection)


class Tagger[T: MusifyItemSettable]:
    """Apply tags to a set of items based on a set of tagging rules."""
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_before_validator_function(
            function=cls.from_config, schema=handler(object)
        )

    @classmethod
    def from_config(cls, config: list[Mapping[str, Any]]) -> Self:
        """Generate the :py:class:`FilterComparers` and :py:class:`Setter` objects from the ``config``"""
        tag_setters = []
        for rule_set in config:
            condition = get_comparers_filter(rule_set["filter"])
            setters = [
                setter_from_config(next(iter(LocalTrackField.from_name(field))), rule_config)
                for field, rule_config in rule_set.items() if field not in ["filter", "field"]
            ]
            tag_setters.append(FilteredSetter[LocalTrack](filter=condition, setters=setters))

        return cls(tag_setters)

    def __init__(self, setters: Collection[FilteredSetter[T]] = ()):
        self.setters = setters

    def set_tags(self, items: Collection[T], collections: Collection[Collection[T]]) -> None:
        """
        Apply setters on the given ``items`` from the given ``collections``.

        :param items: The items to set tags for.
        :param collections: The collections the given items belong to.
            Each item must to exactly one collection for this function to work as expected.
        """
        for setter in self.setters:
            filtered_items = setter.filter(items)

            for item in filtered_items:
                collection = next(iter(coll for coll in collections if item in coll), ())
                setter.set_tags(item, collection)
