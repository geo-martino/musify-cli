from collections.abc import Mapping, Collection
from dataclasses import dataclass, field
from typing import Any, Self

from musify.base import MusifyItemSettable
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.printer import PrettyPrinter
from musify.processors.base import Filter
from musify.processors.filter import FilterDefinedList
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from musify_cli.config.operations.filters import get_comparers_filter
from musify_cli.config.operations.tagger._setter import Setter, setter_from_config


@dataclass
class FilteredSetter[T: MusifyItemSettable](PrettyPrinter):
    """Stores the settings to apply setters to a limited set of filtered items based on a configured filter."""
    filter: Filter[T] = field(default_factory=FilterDefinedList)
    setters: Collection[Setter] = ()

    def set_tags(self, item: T, collection: Collection[T]) -> None:
        """
        Apply setters on the given ``item`` from the given ``collection``.

        :param item: The item to set tags for.
        :param collection: The collection the given item belongs to.
        """
        for setter in self.setters:
            setter.set(item, collection)

    def as_dict(self):
        return {"filter": self.filter, "setters": self.setters}


class Tagger[T: MusifyItemSettable](PrettyPrinter):
    """Apply tags to a set of items based on a set of tagging rules."""

    # noinspection PyUnusedLocal
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        schema = core_schema.no_info_before_validator_function(
            function=cls.from_config,
            schema=handler(object),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda tagger: tagger.json()["rules"],
                info_arg=False,
                return_schema=core_schema.json_schema(),
                when_used="json-unless-none"
            )
        )

        return schema

    @classmethod
    def from_config(cls, config: list[Mapping[str, Any]] | Self) -> Self:
        """Generate the :py:class:`FilterComparers` and :py:class:`Setter` objects from the ``config``"""
        if isinstance(config, Tagger):
            return config

        tag_setters = []
        for rule_set in config:
            if isinstance(rule_set, FilteredSetter):
                setter = rule_set
            else:
                condition = get_comparers_filter(rule_set["filter"])
                setters = [
                    setter_from_config(next(iter(LocalTrackField.from_name(fld))), rule_config)
                    for fld, rule_config in rule_set.items() if fld not in ["filter", "field"]
                ]
                setter = FilteredSetter[LocalTrack](filter=condition, setters=setters)

            tag_setters.append(setter)

        return cls(tag_setters)

    def __init__(self, rules: Collection[FilteredSetter[T]] = ()):
        self.rules = rules

    def set_tags(self, items: Collection[T], collections: Collection[Collection[T]]) -> None:
        """
        Apply setters on the given ``items`` from the given ``collections``.

        :param items: The items to set tags for.
        :param collections: The collections the given items belong to.
            Each item must to exactly one collection for this function to work as expected.
        """
        for rule in self.rules:
            filtered_items = rule.filter(items)

            for item in filtered_items:
                collection = next(iter(coll for coll in collections if item in coll), ())
                rule.set_tags(item, collection)

    def as_dict(self):
        return {"rules": self.rules}
