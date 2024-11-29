from pathlib import Path
from random import choice

import pytest
from musify.libraries.local.library import LIBRARY_CLASSES
from musify.libraries.remote import REMOTE_SOURCES
from pydantic import ValidationError

from musify_cli.config.library import LIBRARY_TYPES, LibrariesConfig, LibraryTarget
from musify_cli.config.library.local import LOCAL_LIBRARY_CONFIG, LocalLibraryConfig, LocalPaths
from musify_cli.config.library.remote import REMOTE_LIBRARY_CONFIG, RemoteLibraryConfig, SpotifyAPIConfig, \
    SpotifyLibraryConfig


def test_all_libraries_supported():
    expected_local = {str(cls.source) for cls in LIBRARY_CLASSES}
    assert expected_local == {str(cls.source) for cls in LOCAL_LIBRARY_CONFIG}

    expected_remote = REMOTE_SOURCES
    assert expected_remote == {str(cls.source) for cls in REMOTE_LIBRARY_CONFIG}

    assert expected_local | expected_remote == LIBRARY_TYPES


@pytest.mark.skip(reason="Test not yet implemented")
def test_create_library_config():
    pass  # TODO


@pytest.mark.skip(reason="Test not yet implemented")
def test_create_library_annotations():
    pass  # TODO


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
            client_id="<CLIENT ID>",
            client_secret="<CLIENT SECRET>",
        )
        return [
            SpotifyLibraryConfig(
                name="remote1",
                type="spotify",
                api=api
            ),
            SpotifyLibraryConfig(
                name="remote2",
                type="spotify",
                api=api
            ),
            SpotifyLibraryConfig(
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

        libraries = LibrariesConfig(local=expected_local, remote=expected_remote)
        assert libraries.local == expected_local
        assert libraries.remote == expected_remote
