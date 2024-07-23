from pathlib import Path

import pytest
from jsonargparse import Namespace

from manager.utils import DatetimeStoreImpl
# noinspection PyProtectedMember
from musify_cli.manager._paths import PathsManager


class TestPathsManager:
    @pytest.fixture
    def config(self, tmp_path: Path) -> Namespace:
        """
        Yields a valid :py:class:`Namespace` representing the config
        for the current manager as a pytest.fixture.
        """
        return Namespace(
            paths=Namespace(
                base=tmp_path,
                backup=Path("/path/to/backup"),
                token="test_token",
                cache="test_cache",
                local_library=Path("/path/to/local_library"),
            )
        )

    @pytest.fixture
    def manager(self, config: Namespace) -> PathsManager:
        """Yields a valid :py:class:`MusifyManager` for the current remote source as a pytest.fixture."""
        return PathsManager(config.paths, dt=DatetimeStoreImpl())

    def test_init_base(self, manager: PathsManager):
        assert manager._base is None
        base_folder = manager.base
        assert manager._base is not None

        # does not generate a new object when called twice even if config changes
        manager.config.base = Path("/path/to/a/new/folder")
        assert manager.base != manager.config.base
        assert id(manager.base) == id(manager._base) == id(base_folder)

    def test_init_backup(self, manager: PathsManager):
        assert manager._backup is None
        backup_folder = manager.backup
        assert manager._backup is not None

        assert backup_folder == Path(manager.config.backup).joinpath(manager._dt.dt.strftime("%Y-%m-%d_%H.%M.%S"))

        # does not generate a new object when called twice even if config changes
        manager.config.backup = Path("/path/to/a/new/folder")
        assert manager.backup != manager.config.backup
        assert id(manager.backup) == id(manager._backup) == id(backup_folder)

    def test_init_cache(self, manager: PathsManager):
        assert manager._cache is None
        cache_folder = manager.cache
        assert manager._cache is not None

        assert cache_folder == Path(manager.config.base).joinpath(manager.config.cache)

        # does not generate a new object when called twice even if config changes
        manager.config.cache = Path("/path/to/a/new/folder")
        assert manager.cache != manager.config.cache
        assert id(manager.cache) == id(manager._cache) == id(cache_folder)

    def test_init_token(self, manager: PathsManager):
        assert manager._token is None
        token_folder = manager.token
        assert manager._token is not None

        assert token_folder == Path(manager.config.base).joinpath(manager.config.token)

        # does not generate a new object when called twice even if config changes
        manager.config.token = Path("/path/to/a/new/folder")
        assert manager.token != manager.config.token
        assert id(manager.token) == id(manager._token) == id(token_folder)

    def test_init_local_library(self, manager: PathsManager):
        assert manager._local_library is None
        local_library_folder = manager.local_library
        assert manager._local_library is not None

        assert local_library_folder == Path(manager.config.local_library)

        # does not generate a new object when called twice even if config changes
        manager.config.local_library = Path("/path/to/a/new/folder")
        assert manager.local_library != manager.config.local_library
        assert id(manager.local_library) == id(manager._local_library) == id(local_library_folder)
