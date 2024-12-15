"""
Core base classes for all config objects.

Defines a config object as either an :py:class:`.Instantiator` of a new object,
or a :py:class:`.Runner` of a specific method.

Also defines core config objects related to common library configuration.
"""
import logging
from abc import ABCMeta, ABC, abstractmethod
from collections.abc import Awaitable
from typing import Any, ClassVar

from musify.libraries.core.object import Library
from musify.logger import MusifyLogger
from musify.processors.filter import FilterComparers
from musify.utils import classproperty
from pydantic import BaseModel, Field, computed_field, ConfigDict

from musify_cli.config.operations.filters import Filter


class Instantiator[T: Any](BaseModel, ABC):
    @abstractmethod
    def create(self, *args, **kwargs) -> T:
        """Instantiate a new instance of the associated object based on the current configuration"""
        raise NotImplementedError


class Runner[T: Any](BaseModel, ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # noinspection PyTypeChecker
        self._logger: MusifyLogger = logging.getLogger(__name__)

    @abstractmethod
    async def run(self, *args, **kwargs) -> T:
        """Run the associated callable based on the current configuration"""
        raise NotImplementedError

    def __call__(self, *args, **kwargs) -> Awaitable[T]:
        return self.run(*args, **kwargs)


class PlaylistsConfig(BaseModel):
    filter: Filter = Field(
        description="The filter to apply to available playlists. Filters on playlist names",
        default_factory=FilterComparers,
    )


class LibraryConfig[T: Library](Instantiator[T], metaclass=ABCMeta):
    model_config = ConfigDict(ignored_types=(classproperty,))

    _library_cls: ClassVar[type[Library]] = Library

    name: str = Field(
        description="The user-assigned name of this library",
    )
    playlists: PlaylistsConfig = Field(
        description="Configures handling for this library's playlists",
        default_factory=PlaylistsConfig,
    )

    @computed_field(description="The source type of the library")
    def type(self) -> str:
        """The source type of the library"""
        return self.source

    # noinspection PyMethodParameters
    @classproperty
    def source(cls) -> str:
        """The source type of the library"""
        return str(cls._library_cls.source)
