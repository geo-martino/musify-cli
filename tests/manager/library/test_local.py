import pytest
from jsonargparse import Namespace
from musify.libraries.local.library import LocalLibrary, MusicBee

from musify_cli.manager.library import LocalLibraryManager, MusicBeeManager
from tests.manager.library.testers import LibraryManagerTester


class TestLocalLibraryManager[T: LocalLibraryManager](LibraryManagerTester[T]):

    @pytest.fixture
    def manager(self) -> T:
        config = Namespace(

        )
        return LocalLibraryManager(name="local", config=config)

    def test_properties(self, manager: T):
        assert manager.source == LocalLibrary.source


class TestMusicBeeManager(LibraryManagerTester[MusicBeeManager]):
    @pytest.fixture
    def manager(self) -> MusicBeeManager:
        config = Namespace(

        )
        return MusicBeeManager(name="musicbee", config=config)

    def test_properties(self, manager: MusicBeeManager):
        assert manager.source == MusicBee.source
