from pathlib import Path
from random import choice

import pytest
from pydantic import ValidationError

from musify_cli.parser.library import LibrariesConfig, LibraryTarget
from musify_cli.parser.library.local import LOCAL_LIBRARY_TYPES, LocalLibraryConfig, LocalPaths
from musify_cli.parser.library.remote import REMOTE_LIBRARY_TYPES, RemoteLibraryConfig, SpotifyAPIConfig


# noinspection PyUnresolvedReferences
def test_all_libraries_supported():
    assert LOCAL_LIBRARY_TYPES == LocalLibraryConfig._type_map.default.keys()
    assert REMOTE_LIBRARY_TYPES == RemoteLibraryConfig._type_map.default.keys()


class TestLibraries:
    @pytest.fixture
    def local_libraries(self, tmp_path: Path) -> list[LocalLibraryConfig]:
        return [
            LocalLibraryConfig(
                name="local1",
                type="local",
                paths=LocalPaths(library=tmp_path)
            ),
            LocalLibraryConfig(
                name="local2",
                type="local",
                paths=LocalPaths(library=tmp_path)
            ),
            LocalLibraryConfig(
                name="local3",
                type="local",
                paths=LocalPaths(library=tmp_path)
            )
        ]

    @pytest.fixture
    def remote_libraries(self) -> list[RemoteLibraryConfig]:
        api = SpotifyAPIConfig(
            client_id="",
            client_secret="",
        )
        return [
            RemoteLibraryConfig[SpotifyAPIConfig](
                name="remote1",
                type="spotify",
                api=api
            ),
            RemoteLibraryConfig[SpotifyAPIConfig](
                name="remote2",
                type="spotify",
                api=api
            ),
            RemoteLibraryConfig[SpotifyAPIConfig](
                name="remote3",
                type="spotify",
                api=api
            )
        ]

    def test_fails_when_no_target_given_on_many_libraries(
            self, local_libraries: list[LocalLibraryConfig], remote_libraries: list[RemoteLibraryConfig]
    ):
        match = "no target specified"
        with pytest.raises(ValidationError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries)
        with pytest.raises(ValidationError, match=match):
            LibrariesConfig(local=local_libraries[0], remote=remote_libraries)
        with pytest.raises(ValidationError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries[0])

    def test_fails_when_target_given_is_invalid(
            self, local_libraries: list[LocalLibraryConfig], remote_libraries: list[RemoteLibraryConfig]
    ):
        match = "target does not correspond to any configured"
        target = LibraryTarget(local="i am not a valid target", remote="I am also not a valid target")
        with pytest.raises(ValidationError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries, target=target)

        valid_local_name = choice([lib.name for lib in local_libraries])
        target = LibraryTarget(local=valid_local_name, remote="invalid name")
        with pytest.raises(ValidationError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries, target=target)

        valid_remote_name = choice([lib.name for lib in remote_libraries])
        target = LibraryTarget(local="invalid name", remote=valid_remote_name)
        with pytest.raises(ValidationError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries, target=target)

    def test_gets_target_libraries(
            self, local_libraries: list[LocalLibraryConfig], remote_libraries: list[RemoteLibraryConfig]
    ):
        expected_local = choice(local_libraries)
        expected_remote = choice(remote_libraries)

        target = LibraryTarget(local=expected_local.name, remote=expected_remote.name)
        libraries = LibrariesConfig(target=target, local=local_libraries, remote=remote_libraries)
        assert libraries.local == expected_local
        assert libraries.remote == expected_remote

        target = LibraryTarget(local=expected_local.name)
        libraries = LibrariesConfig(target=target, local=local_libraries, remote=expected_remote)
        assert libraries.local == expected_local
        assert libraries.remote == expected_remote

        target = LibraryTarget(remote=expected_remote.name)
        libraries = LibrariesConfig(target=target, local=expected_local, remote=remote_libraries)
        assert libraries.local == expected_local
        assert libraries.remote == expected_remote
