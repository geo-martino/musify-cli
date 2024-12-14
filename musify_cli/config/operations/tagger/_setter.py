from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Sequence, Iterable
from string import Formatter
from typing import Any, Self

from aiorequestful.types import UnitCollection
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField as Tag
from musify.printer import PrettyPrinter
from musify.processors.base import Filter
from musify.processors.filter import FilterComparers, FilterDefinedList
from musify.processors.sort import ItemSorter
from musify.utils import to_collection
from musify_cli.config.operations.filters import get_comparers_filter

from musify_cli.config.operations.tagger._getter import Getter, getter_from_config
from musify_cli.exception import ParserError


class Setter(PrettyPrinter, metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]) -> Self:
        """Create a new instance of this Setter type from the given ``config``"""
        raise NotImplementedError

    @classmethod
    def _get_condition_from_dict(cls, config: Mapping[str, Any]) -> FilterComparers:
        when = config.get("when")
        return get_comparers_filter(when)

    def __init__(self, field: Tag, condition: Filter = None):
        self.field = field
        self.condition = condition if condition is not None else FilterDefinedList()

    def _condition_is_valid(self, item: LocalTrack) -> bool:
        return len(self.condition.process([item])) > 0

    @abstractmethod
    def set[T: LocalTrack](self, item: T, collection: Iterable[T]) -> None:
        """Set the value for the given ``item`` found within a given ``collection``"""
        raise NotImplementedError

    def as_dict(self):
        return {"field": self.field, "when": self.condition}


class Value(Setter):
    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        if "value" not in config:
            raise ParserError("No value given", value=config)
        condition = cls._get_condition_from_dict(config)
        return cls(field=field, value=config["value"], condition=condition)

    def __init__(self, field: Tag, value: Any, condition: Filter = None):
        super().__init__(field, condition=condition)
        self.value = value

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        if not self._condition_is_valid(item):
            return
        item[self.field] = self.value

    def as_dict(self):
        return super().as_dict() | {"value": self.value}


class Field(Setter):
    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        if "field" not in config:
            raise ParserError("No value given", value=config)

        value_of_field = next(iter(Tag.from_name(config["field"])))
        condition = cls._get_condition_from_dict(config)
        return cls(field=field, value_of=value_of_field, condition=condition)

    def __init__(self, field: Tag, value_of: Tag, condition: Filter = None):
        super().__init__(field, condition=condition)
        self.value_of = value_of

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        if not self._condition_is_valid(item):
            return
        item[self.field] = item[self.value_of]

    def as_dict(self):
        return super().as_dict() | {"value_of": self.value_of}


class Clear(Setter):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        condition = cls._get_condition_from_dict(config)
        return cls(field=field, condition=condition)

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        if not self._condition_is_valid(item):
            return
        item[self.field] = None


class Join(Setter):
    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        separator = config.get("separator", "")
        fields = list(map(getter_from_config, config.get("values", ())))
        condition = cls._get_condition_from_dict(config)
        return cls(field=field, fields=fields, separator=separator, condition=condition)

    def __init__(self, field: Tag, fields: Sequence[Getter], separator: str, condition: Filter = None):
        super().__init__(field, condition=condition)
        self.fields = fields
        self.separator = separator

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        if not self._condition_is_valid(item):
            return

        values = [getter.get(item) for getter in self.fields]
        item[self.field] = self.separator.join(values)

    def as_dict(self):
        return super().as_dict() | {"fields": self.fields, "separator": self.separator}


class GroupedSetter(Setter, metaclass=ABCMeta):

    def __init__(self, field: Tag, group_by: UnitCollection[Tag] = (), condition: Filter = None):
        super().__init__(field, condition=condition)
        self.group_by: tuple[Tag, ...] = to_collection(group_by)

    @classmethod
    def _get_fields_from_config(cls, config: Mapping[str, Any], key: str) -> Sequence[Tag]:
        fields = to_collection(config.get(key, ()))
        return Tag.from_name(*fields) if fields else ()

    def _group_items[T: LocalTrack](self, item: T, collection: Iterable[T]) -> list[T]:
        return [
            it for it in collection
            if all(it[field] == item[field] for field in self.group_by) and it[self.field] is not None
        ]

    def as_dict(self):
        return super().as_dict() | {"group_by": self.group_by}


class Incremental(GroupedSetter):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        group_by = cls._get_fields_from_config(config, "group")
        sort_by = cls._get_fields_from_config(config, "sort")
        start = int(config.get("start", 1))
        increment = int(config.get("increment", 1))
        condition = cls._get_condition_from_dict(config)

        return cls(
            field=field, group_by=group_by, sort_by=sort_by, start=start, increment=increment, condition=condition
        )

    def __init__(
            self,
            field: Tag,
            group_by: UnitCollection[Tag] = (),
            sort_by: UnitCollection[Tag] | ItemSorter = Tag.FILENAME,
            start: int = 1,
            increment: int = 1,
            condition: Filter = None,
    ):
        super().__init__(field=field, group_by=group_by, condition=condition)
        if not isinstance(sort_by, ItemSorter):
            sort_by = ItemSorter(to_collection(sort_by or field), ignore_words=())

        self.sort_by = sort_by
        self.start = start
        self.increment = increment

    def set[T: LocalTrack](self, item: T, collection: list[T]):
        if not self._condition_is_valid(item):
            return

        group = self._group_items(item, collection)
        self.sort_by.sort(group)
        value = self.start + (group.index(item) * self.increment)
        item[self.field] = value

    def as_dict(self):
        return super().as_dict() | {"sort_by": self.sort_by, "start": self.start, "increment": self.increment}


class GroupedValueSetter(GroupedSetter, metaclass=ABCMeta):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        value_of = next(iter(Tag.from_name(config["field"]))) if "field" in config else field
        group_by = cls._get_fields_from_config(config, "group")
        condition = cls._get_condition_from_dict(config)
        return cls(field=field, value_of=value_of, group_by=group_by, condition=condition)

    def __init__(self, field: Tag, value_of: Tag = None, group_by: UnitCollection[Tag] = (), condition: Filter = None):
        super().__init__(field=field, group_by=group_by, condition=condition)
        self.value_of = value_of or field

    def as_dict(self):
        return super().as_dict() | {"value_of": self.value_of}


class Min(GroupedValueSetter):

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        if not self._condition_is_valid(item):
            return

        items = self._group_items(item=item, collection=collection)
        values = {it[self.field] for it in items}
        if values:
            item[self.field] = min(values)


class Max(GroupedValueSetter):

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        if not self._condition_is_valid(item):
            return

        items = self._group_items(item=item, collection=collection)
        values = {it[self.field] for it in items}
        if values:
            item[self.field] = max(values)


class Template(Setter):
    @property
    def template(self) -> str:
        """The template string to use when formatting the final string value"""
        return self._template

    @template.setter
    def template(self, value: str):
        self._required_fields = set(fn for _, fn, _, _ in Formatter().parse(value) if fn is not None)
        # noinspection PyTypeChecker
        missing_fields: set[str] = self._required_fields - set(self.fields) - Tag.__tags__
        if missing_fields:
            raise ParserError(f"Template contains fields which have not been configured: {', '.join(missing_fields)}")

        self._template = value

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        if "template" not in config:
            raise ParserError("No template given", value=config)

        template = config["template"]
        fields = {
            key: getter_from_config(conf)
            for key, conf in config.items() if key not in {"operation", "template"}
        }
        condition = cls._get_condition_from_dict(config)
        return cls(field=field, template=template, fields=fields, condition=condition)

    def __init__(self, field: Tag, template: str, fields: Mapping[str, Getter] = None, condition: Filter = None):
        super().__init__(field, condition=condition)
        self.fields = fields if fields is not None else {}
        self.template = template

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]) -> None:
        if not self._condition_is_valid(item):
            return

        values_map = {key: getter.get(item) for key, getter in self.fields.items()}
        for field in self._required_fields - set(self.fields):
            values_map[field] = item[field]

        for key, val in values_map.items():
            if val is None:
                values_map[key] = ""

        item[self.field] = self.template.format_map(values_map)

    def as_dict(self):
        return super().as_dict() | {"fields": self.fields, "template": self.template}


SETTERS: list[type[Setter]] = [Clear, Min, Max, Join, Incremental, Template]


def setter_from_config(field: Tag, config: Any | Mapping[str, Any]) -> Setter:
    """Factory method to create an appropriate :py:class:`.Setter` object from the given ``config``"""
    if not isinstance(config, Mapping):
        return Value(field=field, value=config)

    setters_map = {cls.__name__.lower(): cls for cls in SETTERS}

    operation = config.get("operation")
    if operation not in setters_map:
        if "value" in config:
            return Value.from_dict(field, config)
        elif "field" in config:
            return Field.from_dict(field, config)
        raise ParserError("Unrecognised {key}", key="operation", value=operation)

    return setters_map[operation].from_dict(field, config)
