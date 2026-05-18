from collections.abc import Generator
from unittest.mock import patch, PropertyMock, Mock

import pytest
from faker import Faker
from mytunes.core.library import Library
from mytunes.core.playlist import Playlist
from mytunes.local.album import LocalAlbumCollection
from mytunes.local.folder import Folder
from mytunes.local.library import LocalLibrary
from mytunes.processors.filters.values import NameFilter

from mytunes_cli.operations._filters import HasPlaylistFilter, HasAlbumFilter, HasFolderFilter
from mytunes_cli.state import GlobalState


# noinspection PyAbstractClass
class TestHasPlaylistFilter:
    @pytest.fixture
    def model(self, state: GlobalState) -> HasPlaylistFilter:
        return HasPlaylistFilter(state=state)

    @pytest.fixture(autouse=True)
    def items(self, library: Library, playlists: list[Playlist]) -> list[Playlist]:
        library.playlists._extend(playlists)
        return playlists

    def test_get_all(self, model: HasPlaylistFilter, library: Library, playlists: list[Playlist]):
        model.filter = None
        assert sorted(model._get_playlists(library)) == sorted(playlists)

    def test_get_filtered(self, model: HasPlaylistFilter, library: Library, playlists: list[Playlist], faker: Faker):
        filtered = faker.random_elements(playlists, unique=True)
        model.filter = NameFilter(values={item.name for item in filtered})

        assert sorted(model._get_playlists(library)) == sorted(filtered)


# noinspection PyAbstractClass
class TestHasAlbumFilter:
    @pytest.fixture
    def model(self) -> HasAlbumFilter:
        return HasAlbumFilter()

    @pytest.fixture(autouse=True)
    def mock_items(self, local_albums: list[LocalAlbumCollection]) -> Generator[Mock]:
        with patch.object(LocalLibrary, "albums", return_value=local_albums, new_callable=PropertyMock) as mock_items:
            yield mock_items

    def test_get_all(
            self, model: HasAlbumFilter, local_library: LocalLibrary, local_albums: list[LocalAlbumCollection]
    ):
        model.filter = None
        assert sorted(model._get_albums(local_library)) == sorted(local_albums)

    def test_get_filtered(
            self,
            model: HasAlbumFilter,
            local_library: LocalLibrary,
            local_albums: list[LocalAlbumCollection],
            faker: Faker
    ):
        filtered = faker.random_elements(local_albums, unique=True)
        model.filter = NameFilter(values={item.name for item in filtered})

        assert sorted(model._get_albums(local_library)) == sorted(filtered)


# noinspection PyAbstractClass
class TestHasFolderFilter:
    @pytest.fixture
    def model(self) -> HasFolderFilter:
        return HasFolderFilter()

    @pytest.fixture(autouse=True)
    def mock_items(self, folders: list[Folder]) -> Generator[Mock]:
        with patch.object(LocalLibrary, "folders", return_value=folders, new_callable=PropertyMock) as mock_items:
            yield mock_items

    def test_get_all(self, model: HasFolderFilter, local_library: LocalLibrary, folders: list[Folder]):
        model.filter = None
        assert sorted(model._get_folders(local_library)) == sorted(folders)

    def test_get_filtered(
            self, model: HasFolderFilter, local_library: LocalLibrary, folders: list[Folder], faker: Faker
    ):
        filtered = faker.random_elements(folders, unique=True)
        model.filter = NameFilter(values={item.name for item in filtered})

        assert sorted(model._get_folders(local_library)) == sorted(filtered)
