from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch, PropertyMock

import pytest
from faker import Faker
from mytunes.core.library import Library, RemoteLibrary, RemoteMutableLibrary
from mytunes.core.playlist import MutablePlaylist
from mytunes.core.track import RemoteTrack
from mytunes.core.user import RemoteUser
from mytunes.local.album import LocalAlbumCollection
from mytunes.local.folder import Folder
from mytunes.local.library import LocalLibrary
from mytunes.local.track import LocalTrack

from mytunes_cli.state import GlobalState
from mytunes_cli.state.paths import GlobalPaths
from remote import MockRemoteMutableLibrary, MockRemoteAPI, SimpleURI


@pytest.fixture
def state(libraries: dict[str, Library], faker: Faker, tmp_path: Path) -> GlobalState:
    return GlobalState(
        paths=GlobalPaths(application=tmp_path),
        libraries=libraries,
        dry_run=faker.boolean(),
    )


@pytest.fixture
def local_libraries(faker: Faker) -> dict[str, LocalLibrary]:
    return {faker.name(): LocalLibrary() for _ in range(faker.random_int(1, 10))}


@pytest.fixture
def local_library_name(local_libraries: dict[str, LocalLibrary], faker: Faker) -> str:
    return faker.random_element(local_libraries.keys())


@pytest.fixture
def local_library(local_library_name: str, local_libraries: dict[str, LocalLibrary]) -> LocalLibrary:
    return local_libraries[local_library_name]


@pytest.fixture
def remote_libraries(faker: Faker) -> Generator[dict[str, RemoteMutableLibrary]]:
    libraries = {
        faker.name(): MockRemoteMutableLibrary(api=MockRemoteAPI())
        for _ in range(faker.random_int(1, 10))
    }

    # need to patch out the user property for some logging purposes
    user = RemoteUser(name=faker.name(), uri=SimpleURI.create_random(RemoteUser.type))
    with patch.object(RemoteLibrary, "user", return_value=user, new_callable=PropertyMock):
        yield libraries


@pytest.fixture
def remote_library_name(remote_libraries: dict[str, RemoteMutableLibrary], faker: Faker) -> str:
    return faker.random_element(remote_libraries.keys())


@pytest.fixture
def remote_library(remote_library_name: str, remote_libraries: dict[str, RemoteMutableLibrary]) -> RemoteMutableLibrary:
    return remote_libraries[remote_library_name]


@pytest.fixture
def libraries(local_libraries: dict[str, LocalLibrary], remote_libraries: dict[str, RemoteMutableLibrary]):
    return local_libraries | remote_libraries


@pytest.fixture
def library_name(libraries: dict[str, Library], faker: Faker) -> str:
    return faker.random_element(libraries.keys())


@pytest.fixture
def library(library_name: str, libraries: dict[str, Library]) -> Library:
    return libraries[library_name]


@pytest.fixture
def local_tracks(faker: Faker) -> list[LocalTrack]:
    return [
        LocalTrack(name=faker.sentence().rstrip("."), path=faker.file_path(extension=".mp3"))
        for _ in range(faker.random_int(10, 30))
    ]


@pytest.fixture
def remote_tracks(faker: Faker) -> list[RemoteTrack]:
    return [
        RemoteTrack(name=faker.sentence().rstrip("."), uri=SimpleURI.create_random(RemoteTrack.type))
        for _ in range(faker.random_int(10, 30))
    ]


@pytest.fixture
def playlists(faker: Faker) -> list[MutablePlaylist]:
    return [MutablePlaylist(name=faker.sentence().rstrip(".")) for _ in range(faker.random_int(10, 30))]


@pytest.fixture
def local_albums(faker: Faker) -> list[LocalAlbumCollection]:
    return [LocalAlbumCollection(name=faker.sentence().rstrip(".")) for _ in range(faker.random_int(10, 30))]


@pytest.fixture
def folders(faker: Faker) -> list[Folder]:
    return [Folder(name=faker.sentence().rstrip(".")) for _ in range(faker.random_int(10, 30))]
