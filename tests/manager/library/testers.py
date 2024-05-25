from abc import ABC, abstractmethod
from pathlib import Path
from random import shuffle, sample

from jsonargparse import Namespace
from musify.core.enum import MusifyEnum

# noinspection PyProtectedMember
from musify_cli.manager.library._core import LibraryManager


class LibraryManagerTester[T: LibraryManager](ABC):
    """Run generic tests for :py:class:`LibraryManager` implementations"""

    @abstractmethod
    def load_types(self) -> type[MusifyEnum]:
        """Yields the enum type that represent the load types for the current remote source as a pytest.fixture."""
        raise NotImplementedError

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

    @staticmethod
    async def test_load_with_types(manager_mock: T, load_types: type[MusifyEnum]):
        library = manager_mock.library
        assert not library.load_calls
        assert not manager_mock.types_loaded

        types = load_types.all()
        shuffle(types)

        await manager_mock.load(types=types[0])
        assert manager_mock.types_loaded == {types[0]}
        assert library.load_calls == [types[0].name.lower()]

        await manager_mock.load(types=types[1:])
        assert manager_mock.types_loaded == set(types)
        expected_calls = [types[0].name.lower()] + [t.name.lower() for t in load_types.all() if t != types[0]]
        assert library.load_calls == expected_calls

        # does not call any load methods twice
        await manager_mock.load(types=types)
        assert manager_mock.types_loaded == set(types)
        assert library.load_calls == expected_calls

        # does call load methods twice on force
        await manager_mock.load(types=types, force=True)
        assert manager_mock.types_loaded == set(types)
        expected_calls += [enum.name.lower() for enum in load_types.all()]
        assert library.load_calls == expected_calls

    @staticmethod
    async def test_load_all(manager_mock: T, load_types: type[MusifyEnum]):
        library = manager_mock.library
        assert not library.load_calls
        assert not manager_mock.types_loaded

        await manager_mock.load()
        assert manager_mock.types_loaded == set(load_types.all())
        assert library.load_calls == ["all"]

        # does not call any load methods twice
        await manager_mock.load()
        assert manager_mock.types_loaded == set(load_types.all())
        assert library.load_calls == ["all"]

        types = sample(load_types.all(), k=2)
        await manager_mock.load(types=types)
        assert manager_mock.types_loaded == set(load_types.all())
        assert library.load_calls == ["all"]

        # does call load methods twice on force
        await manager_mock.load(force=True)
        assert manager_mock.types_loaded == set(load_types.all())
        assert library.load_calls == ["all"] * 2

        await manager_mock.load(types=types, force=True)
        assert manager_mock.types_loaded == set(load_types.all())
        assert library.load_calls == ["all"] * 2 + [t.name.lower() for t in sorted(types, key=lambda t: t.value)]

    @staticmethod
    async def test_load_all_after_types(manager_mock: T, load_types: type[MusifyEnum]):
        library = manager_mock.library
        assert not library.load_calls
        assert not manager_mock.types_loaded

        types = load_types.all()
        shuffle(types)

        await manager_mock.load(types=types[0])
        assert manager_mock.types_loaded == {types[0]}
        assert library.load_calls == [types[0].name.lower()]

        await manager_mock.load(types=types[1])
        assert manager_mock.types_loaded == set(types[:2])
        expected_calls = [t.name.lower() for t in types[:2]]
        assert library.load_calls == expected_calls

        await manager_mock.load()
        assert manager_mock.types_loaded == set(types)
        expected_calls += [t.name.lower() for t in load_types.all() if t not in types[:2]]
        assert library.load_calls == expected_calls
