from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Sequence, Iterable
from string import Formatter
from typing import Any

from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField as Tag
from musify.processors.sort import ItemSorter
from musify.types import UnitCollection
from musify.utils import to_collection

from musify_cli.exception import ParserError
from musify_cli.tagger.getter import Getter, getter_from_config


class Setter(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        raise NotImplementedError

    def __init__(self, field: Tag):
        self.field = field

    @abstractmethod
    def set[T: LocalTrack](self, item: T, collection: Iterable[T]) -> None:
        raise NotImplementedError


class Value(Setter):
    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        if "value" not in config:
            raise ParserError("No value given", value=config)
        return cls(field=field, value=config["value"])

    def __init__(self, field: Tag, value: Any):
        super().__init__(field)
        self.value = value

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        item[self.field] = self.value


class Field(Setter):
    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        if "field" not in config:
            raise ParserError("No value given", value=config)
        value_of_field = next(iter(Tag.from_name(config["field"])))
        return cls(field=field, value_of=value_of_field)

    def __init__(self, field: Tag, value_of: Tag):
        super().__init__(field)
        self.value_of = value_of

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        item[self.field] = item[self.value_of]


class Clear(Setter):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        return cls(field=field)

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        item[self.field] = None


class Join(Setter):
    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        separator = config.get("separator", "")
        fields = list(map(getter_from_config, config.get("values", ())))
        return cls(field=field, fields=fields, separator=separator)

    def __init__(self, field: Tag, fields: Sequence[Getter], separator: str):
        super().__init__(field)
        self.fields = fields
        self.separator = separator

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        values = [getter.get(item) for getter in self.fields]
        item[self.field] = self.separator.join(values)


class GroupedSetter(Setter, metaclass=ABCMeta):

    def __init__(self, field: Tag, group_by: UnitCollection[Tag] = ()):
        super().__init__(field)
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


class Incremental(GroupedSetter):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        group_by = cls._get_fields_from_config(config, "group")
        sort_by = cls._get_fields_from_config(config, "sort")
        start = int(config.get("start", 1))
        increment = int(config.get("increment", 1))
        return cls(field=field, group_by=group_by, sort_by=sort_by, start=start, increment=increment)

    def __init__(
            self,
            field: Tag,
            group_by: UnitCollection[Tag] = (),
            sort_by: UnitCollection[Tag] | ItemSorter = Tag.FILENAME,
            start: int = 1,
            increment: int = 1,
    ):
        super().__init__(field=field, group_by=group_by)
        if not isinstance(sort_by, ItemSorter):
            sort_by = ItemSorter(to_collection(sort_by or field))

        self.sort_by = sort_by
        self.start = start
        self.increment = increment

    def set[T: LocalTrack](self, item: T, collection: list[T]):
        group = self._group_items(item, collection)
        self.sort_by.sort(group)
        value = self.start + (group.index(item) * self.increment)
        item[self.field] = value


class GroupedValueSetter(GroupedSetter, metaclass=ABCMeta):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        value_of = next(iter(Tag.from_name(config["field"]))) if "field" in config else field
        group_by = cls._get_fields_from_config(config, "group")
        return cls(field=field, value_of=value_of, group_by=group_by)

    def __init__(self, field: Tag, value_of: Tag = None, group_by: UnitCollection[Tag] = ()):
        super().__init__(field=field, group_by=group_by)
        self.value_of = value_of or field


class Min(GroupedValueSetter):

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        items = self._group_items(item=item, collection=collection)
        item[self.field] = min(it[self.field] for it in items)


class Max(GroupedValueSetter):

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        items = self._group_items(item=item, collection=collection)
        item[self.field] = max(it[self.field] for it in items)


class Template(Setter):
    @property
    def template(self) -> str:
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
        return cls(field=field, template=template, fields=fields)

    def __init__(self, field: Tag, template: str, fields: Mapping[str, Getter]):
        super().__init__(field)
        self.fields = fields
        self.template = template

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]) -> None:
        values_map = {key: getter.get(item) for key, getter in self.fields.items()}
        for field in self._required_fields - set(self.fields):
            values_map[field] = item[field]

        for key, val in values_map.items():
            if val is None:
                values_map[key] = ""

        item[self.field] = self.template.format_map(values_map)


SETTERS: list[type[Setter]] = [Clear, Min, Max, Join, Incremental, Template]


def setter_from_config(field: Tag, config: Any | Mapping[str, Any]) -> Setter:
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
