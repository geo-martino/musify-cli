from abc import ABC, abstractmethod
from pathlib import Path

from jsonargparse import Namespace

# noinspection PyProtectedMember
from musify_cli.manager.library._core import LibraryManager


class LibraryManagerTester[T: LibraryManager](ABC):
    @abstractmethod
    def config(self, tmp_path: Path) -> Namespace:
        """
        Yields a valid :py:class:`Namespace` representing the config
        for the current remote source as a pytest.fixture.
        """
        raise NotImplementedError

    @abstractmethod
    def manager(self, config: Namespace) -> T:
        """Yields a valid :py:class:`LibraryManager` for the current remote source as a pytest.fixture."""
        raise NotImplementedError

    @abstractmethod
    def manager_mock(self, manager: T) -> T:
        """
        Replace the instantiated library from the given ``manager`` with a mocked library.
        Yields the modified ``manager`` as a pytest.fixture.
        """
        raise NotImplementedError
