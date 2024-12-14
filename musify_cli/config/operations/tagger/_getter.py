"""
Handles getting of tag values from items based on a set of configurable rules.
"""
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from typing import Any, Self

from musify.base import MusifyItem
from musify.field import TagField, TagFields
from musify.libraries.local.base import LocalItem
from musify.printer import PrettyPrinter
from musify.processors.base import Filter
from musify.processors.filter import FilterComparers

from musify_cli.config.operations.filters import get_comparers_filter
from musify_cli.exception import ParserError


class Getter(PrettyPrinter, metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def from_dict(cls, config: Mapping[str, Any]):
        """Create a new instance of this Getter type from the given ``config``"""
        raise NotImplementedError

    def __init__(self, field: TagField | None):
        self.field = field

    @abstractmethod
    def get[T: MusifyItem](self, item: T) -> Any:
        """Get the value from the given ``item``"""
        raise NotImplementedError

    def as_dict(self):
        return {"field": self.field}


class TagGetter(Getter):
    @classmethod
    def from_field(cls, field: str) -> Self:
        """Create a new instance of this Getter type from the given ``field``"""
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
        if isinstance(leading_zeros := config.get("leading_zeros"), int) or leading_zeros is None:
            return leading_zeros
        return TagFields.from_name(leading_zeros)[0]

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

    def as_dict(self):
        return super().as_dict() | {"leading_zeros": self.leading_zeros}


class ConditionalGetter(TagGetter):
    @classmethod
    def from_dict(cls, config: Mapping[str, Any]):
        when = config.get("when", {})
        filter_ = get_comparers_filter(when)

        field_str = config.get("field")
        field = next(iter(TagFields.from_name(field_str))) if field_str else None

        value = config.get("value", "")
        leading_zeros = cls._get_leading_zeros_from_config(config)
        return cls(condition=filter_, field=field, value=value, leading_zeros=leading_zeros)

    def __init__(
            self,
            field: TagField | None = None,
            condition: Filter = None,
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

    def as_dict(self):
        return super().as_dict() | {"condition": self.condition.as_dict(), "value": self.value}


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

    def as_dict(self):
        return super().as_dict() | {"parent": self.parent}


GETTERS: list[type[Getter]] = [PathGetter]


def getter_from_config(config: str | Mapping[str, Any]) -> Getter:
    """Factory method to create an appropriate :py:class:`.Getter` object from the given ``config``"""
    if not isinstance(config, Mapping):
        return TagGetter.from_field(config)

    getters_map: dict[str, type[Getter]] = {
        cls.__name__.replace("Getter", "").lower(): cls for cls in GETTERS
    }

    if "when" in config:
        return ConditionalGetter.from_dict(config)
    return getters_map.get(config.get("field"), TagGetter).from_dict(config)
