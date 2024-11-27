import logging
import logging.config
from abc import ABC, abstractmethod
from functools import cached_property

from musify.base import MusifyObject
from musify.libraries.core.object import Library
from musify.logger import MusifyLogger
from musify.processors.filter import FilterComparers
from musify.types import UnitCollection, MusifyEnum

from musify_cli.config.library import LibraryConfig


class LibraryManager[T: LibraryConfig](ABC):
    """Generic base class for instantiating and managing a library and related objects from a given ``config``."""

    def __init__(self, config: T, dry_run: bool = True):
        # noinspection PyTypeChecker
        self.logger: MusifyLogger = logging.getLogger(__name__)

        self.initialised = False

        self.config = config
        self.dry_run = dry_run

    @property
    def name(self) -> str:
        """The user-defined name of the library"""
        return self.config.name

    @cached_property
    @abstractmethod
    def source(self) -> str:
        """The name of the source currently being used for this library"""
        raise NotImplementedError

    @cached_property
    @abstractmethod
    def library(self) -> Library:
        """The initialised library"""
        raise NotImplementedError

    @property
    def playlist_filter(self) -> FilterComparers[str | MusifyObject] | None:
        """The configured :py:class:`FilterComparers` to use when filtering playlists by name"""
        return self.config.playlists.filter if self.config.playlists.filter.ready else None

    @abstractmethod
    async def load(self, types: UnitCollection[MusifyEnum] = (), force: bool = False) -> None:
        """
        Load items/collections in the instantiated library based on the given ``types``.

        :param types: The types of items/collections to load.
        :param force: Whether to reload the given ``types`` even if they have already been loaded before.
            When False, only load the ``types`` that have not been loaded.
        """
        raise NotImplementedError
