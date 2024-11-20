from abc import ABCMeta, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from musify.base import MusifyItem
from musify.field import Field, Fields
from musify.libraries.local.base import LocalItem

from musify_cli.exception import ParserError


class Getter(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def from_dict(cls, config: str | Mapping[str, Any]):
        raise NotImplementedError

    def __init__(self, field: Field):
        self.field = field

    @abstractmethod
    def get[T: MusifyItem](self, item: T) -> Any:
        raise NotImplementedError


class TagGetter(Getter):
    @classmethod
    def from_dict(cls, config: str | Mapping[str, Any]):
        if isinstance(config, Mapping):
            config = config["field"]
        field = next(iter(Fields.from_name(config)))
        return cls(field)

    def __init__(self, field: Field):
        self.field = field

    def get[T: MusifyItem](self, item: T) -> Any:
        return item[self.field]


class PathGetter(Getter):

    @classmethod
    def from_dict(cls, config: str | Mapping[str, Any]):
        parent = int(config.get("parent", 0))
        return cls(parent=parent)

    def __init__(self, parent: int = 0):
        if parent < 0:
            raise ParserError("Parent value must be >= 0", key="parent", value=parent)

        super().__init__(field=Fields.PATH)
        self.parent = parent

    def get[T: LocalItem](self, item: LocalItem) -> Any:
        return item.path.parts[-self.parent - 1]


GETTERS: list[type[Getter]] = [PathGetter]
GETTERS_MAP: dict[str | None, type[Getter]] = {None: TagGetter} | {
    cls.__name__.replace("Getter", "").lower(): cls for cls in GETTERS
}
