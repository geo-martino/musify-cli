from abc import ABC, abstractmethod

# noinspection PyProtectedMember
from musify_cli.manager.library._core import LibraryManager


class LibraryManagerTester[T: LibraryManager](ABC):
    @abstractmethod
    def manager(self) -> T:
        """Yields a valid :py:class:`LibraryManager` for the current remote source as a pytest.fixture."""
        raise NotImplementedError
