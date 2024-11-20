from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Sequence, Iterable
from typing import Any

from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField as Tag
from musify.processors.sort import ItemSorter
from musify.types import UnitCollection
from musify.utils import to_collection

from musify_cli.tagger.getter import Getter, GETTERS_MAP, TagGetter


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


class Clear(Setter):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        return cls(field=field)

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        item[self.field] = None


class GroupedValueSetter(Setter, metaclass=ABCMeta):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        value_of = next(iter(Tag.from_name(config["field"]))) if "field" in config else field
        group = to_collection(config.get("group", ()))
        group_by = Tag.from_name(*group) if group else ()
        return cls(field=field, value_of=value_of, group_by=group_by)

    def __init__(self, field: Tag, value_of: Tag = None, group_by: UnitCollection[Tag] = ()):
        super().__init__(field)
        self.value_of = value_of or field
        self.group_by: tuple[Tag, ...] = to_collection(group_by)

    def _group_items[T: LocalTrack](self, item: T, collection: Iterable[T]) -> list[Any]:
        return [
            it[self.field] for it in collection
            if all(it[field] == item[field] for field in self.group_by) and it[self.field] is not None
        ]


class Min(GroupedValueSetter):

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        values = self._group_items(item=item, collection=collection)
        item[self.field] = min(values)


class Max(GroupedValueSetter):

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        values = self._group_items(item=item, collection=collection)
        item[self.field] = max(values)


class Join(Setter):
    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        separator = config.get("separator", "")
        fields = [GETTERS_MAP.get(conf["field"], TagGetter).from_dict(conf) for conf in config.get("values", ())]
        return cls(field=field, fields=fields, separator=separator)

    def __init__(self, field: Tag, fields: Sequence[Getter], separator: str):
        super().__init__(field)
        self.fields = fields
        self.separator = separator

    def set[T: LocalTrack](self, item: T, collection: Iterable[T]):
        values = [getter.get(item) for getter in self.fields]
        item[self.field] = self.separator.join(values)


class Incremental(Setter):

    @classmethod
    def from_dict(cls, field: Tag, config: Mapping[str, Any]):
        sort = to_collection(config.get("sort", ()))
        sort_by = Tag.from_name(*sort) if sort else (field,)
        start = int(config.get("start", 1))
        increment = int(config.get("increment", 1))
        return cls(field=field, sort_by=sort_by, start=start, increment=increment)

    def __init__(
            self,
            field: Tag,
            sort_by: UnitCollection[Tag] | ItemSorter = Tag.FILENAME,
            start: int = 1,
            increment: int = 1,
    ):
        super().__init__(field)
        if not isinstance(sort_by, ItemSorter):
            sort_by = ItemSorter(to_collection(sort_by))

        self.sort_by = sort_by
        self.start = start
        self.increment = increment

    def set[T: LocalTrack](self, item: T, collection: list[T]):
        self.sort_by.sort(collection)
        print(self.start, collection.index(item), self.increment)
        value = self.start + (collection.index(item) * self.increment)
        item[self.field] = value


SETTERS: list[type[Setter]] = [Clear, Min, Max, Join, Incremental]
SETTERS_MAP = {cls.__name__.lower(): cls for cls in SETTERS}
