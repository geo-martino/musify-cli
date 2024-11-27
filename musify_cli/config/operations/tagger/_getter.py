from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from typing import Any, Self

from musify.base import MusifyItem
from musify.field import TagField, TagFields
from musify.libraries.local.base import LocalItem
from musify.processors.filter import FilterComparers

from musify_cli.config.operations.filters import get_comparers_filter
from musify_cli.exception import ParserError


class Getter(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def from_dict(cls, config: Mapping[str, Any]):
        raise NotImplementedError

    def __init__(self, field: TagField | None):
        self.field = field

    @abstractmethod
    def get[T: MusifyItem](self, item: T) -> Any:
        raise NotImplementedError


class TagGetter(Getter):
    @classmethod
    def from_field(cls, field: str) -> Self:
        field = next(iter(TagFields.from_name(field)))
        return cls(field)

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]):
        if "field" not in config:
            raise ParserError("No field given", value=config)

        field = next(iter(TagFields.from_name(config["field"])))
        leading_zeros = cls._get_leading_zeros_from_config(config)
        return cls(field, leading_zeros=leading_zeros)

    @classmethod
    def _get_leading_zeros_from_config(cls, config: Mapping[str, Any]) -> int | TagField | None:
        return config.get("leading_zeros")

    def __init__(self, field: TagField | None, leading_zeros: int | TagField = None):
        super().__init__(field)
        self.leading_zeros = leading_zeros

    def _add_leading_zeros[T: MusifyItem](self, item: T, value: str) -> str:
        if isinstance(self.leading_zeros, TagField):
            tag_value = item[self.leading_zeros]
            width = len(str(tag_value)) if tag_value is not None else 0
        else:
            width = self.leading_zeros

        return value.zfill(width)

    def get[T: MusifyItem](self, item: T) -> Any:
        value = item[self.field] if self.field is not None else None
        if value is not None and self.leading_zeros is not None:
            value = self._add_leading_zeros(item, str(value))
        return value


class ConditionalGetter(TagGetter):
    @classmethod
    def from_dict(cls, config: Mapping[str, Any]):
        when = config.get("when", {})
        conditional_field_str: str | None = when.pop("field", None)
        conditional_field = next(iter(TagFields.from_name(conditional_field_str))) if conditional_field_str else None

        filter_ = get_comparers_filter(when)
        for comparer in filter_.comparers:
            comparer.field = conditional_field

        field_str = config.get("field")
        field = next(iter(TagFields.from_name(field_str))) if field_str else None

        value = config.get("value", "")
        leading_zeros = cls._get_leading_zeros_from_config(config)
        return cls(condition=filter_, field=field, value=value, leading_zeros=leading_zeros)

    def __init__(
            self,
            field: TagField | None = None,
            condition: FilterComparers = None,
            value: str = "",
            leading_zeros: int | TagField = None
    ):
        super().__init__(field, leading_zeros=leading_zeros)
        self.condition = condition if condition is not None else FilterComparers()
        self.value = value

    def get[T: MusifyItem](self, item: T) -> Any:
        if not self.condition.process([item]):
            return None
        return super().get(item) if self.field is not None else self.value


class PathGetter(Getter):

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]):
        parent = int(config.get("parent", 0))
        return cls(parent=parent)

    def __init__(self, parent: int = 0):
        if parent < 0:
            raise ParserError("Parent value must be >= 0", key="parent", value=parent)

        super().__init__(field=TagFields.PATH)
        self.parent = parent

    def get[T: LocalItem](self, item: T) -> Any:
        return item.path.parts[-self.parent - 1]


GETTERS: list[type[Getter]] = [PathGetter]


def getter_from_config(config: str | Mapping[str, Any]) -> Getter:
    if not isinstance(config, Mapping):
        return TagGetter.from_field(config)

    getters_map: dict[str, type[Getter]] = {
        cls.__name__.replace("Getter", "").lower(): cls for cls in GETTERS
    }

    if "when" in config:
        return ConditionalGetter.from_dict(config)
    return getters_map.get(config.get("field"), TagGetter).from_dict(config)
