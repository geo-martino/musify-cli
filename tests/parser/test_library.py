from collections.abc import Collection
from copy import deepcopy
from pathlib import Path, PureWindowsPath, PurePosixPath
from random import choice
from typing import Any

import pytest
from musify.libraries.local.library import MusicBee
from musify.utils import to_collection
from pydantic import ValidationError

from musify_cli.exception import ParserError
# noinspection PyProtectedMember
from musify_cli.parser.library import LOCAL_LIBRARY_TYPES, REMOTE_LIBRARY_TYPES, RemoteLibraryConfig, \
    LocalLibraryPaths, MusicBeePaths, LocalLibraryPathsParser, LocalPaths, APIConfig, SpotifyAPIConfig, LibrariesConfig, \
    LibraryTarget, LocalLibraryConfig
from utils import random_str


# noinspection PyUnresolvedReferences
def test_all_libraries_supported():
    assert LOCAL_LIBRARY_TYPES == LocalLibraryConfig._type_map.default.keys()
    assert REMOTE_LIBRARY_TYPES == RemoteLibraryConfig._type_map.default.keys()


class TestLocalLibraryPaths:

    paths = dict(
        win=(r"C:\windows\path1", r"C:\windows\path2"),
        lin=["/linux/path1", "/linux/path2"],
        mac={"/mac/path1", "/mac/path2"},
    )

    @classmethod
    def get_valid_paths(cls, tmp_path: Path) -> dict[str, Collection[str]]:
        paths = deepcopy(cls.paths)
        paths[str(LocalLibraryPathsParser._platform_key)] = [str(tmp_path)]
        return paths

    @pytest.fixture
    def valid_paths(self, tmp_path: Path) -> dict[str, Collection[str]]:
        return self.get_valid_paths(tmp_path)

    @pytest.fixture
    def invalid_paths(self) -> dict[str, Collection[str]]:
        return deepcopy(self.paths)

    @pytest.fixture
    def valid_model(self, valid_paths: dict[str, Collection[str]]) -> LocalLibraryPaths:
        return LocalLibraryPaths(**valid_paths)

    # noinspection PyStatementEffect
    def test_init_fails(self, invalid_paths: dict[str, Collection[str]]):
        with pytest.raises(ParserError, match="are not valid directories"):
            LocalLibraryPaths(**invalid_paths)

        invalid_paths.pop(str(LocalLibraryPathsParser._platform_key))
        with pytest.raises(ParserError, match="No valid paths found for the current platform"):
            LocalLibraryPaths(**invalid_paths)

    def test_properties(self, valid_model: LocalLibraryPaths, valid_paths: dict[str, Collection[str]]):
        assert valid_model.win == tuple(PureWindowsPath(path) for path in valid_paths["win"])
        assert valid_model.lin == tuple(PurePosixPath(path) for path in valid_paths["lin"])
        assert valid_model.mac == tuple(PurePosixPath(path) for path in valid_paths["mac"])

        assert valid_model.paths == tuple(Path(path) for path in valid_paths[str(valid_model._platform_key)])
        assert all(path not in valid_model.paths for path in valid_model.others)

    def test_properties_on_unit_path(self, valid_paths: dict[str, Collection[str]]):
        paths = {k: next(iter(v)) for k, v in valid_paths.items()}
        model = LocalLibraryPaths(**paths)

        assert isinstance(model.win, tuple)
        assert isinstance(model.lin, tuple)
        assert isinstance(model.mac, tuple)


class TestMusicBeePaths:

    paths = dict(
        win=r"C:\windows\path",
        lin="/linux/path",
        mac="/mac/path",
    )

    @classmethod
    def get_valid_paths(cls, tmp_path: Path) -> dict[str, str]:
        tmp_path.joinpath(MusicBee.xml_library_path).touch(exist_ok=True)
        tmp_path.joinpath(MusicBee.xml_settings_path).touch(exist_ok=True)

        paths = deepcopy(cls.paths)
        paths[str(MusicBeePaths._platform_key)] = str(tmp_path)
        return paths

    @pytest.fixture
    def valid_paths(self, tmp_path: Path) -> dict[str, str]:
        return self.get_valid_paths(tmp_path)

    @pytest.fixture
    def invalid_paths(self) -> dict[str, Collection[str]]:
        return deepcopy(self.paths)

    @pytest.fixture
    def valid_model(self, valid_paths: dict[str, str]) -> MusicBeePaths:
        return MusicBeePaths(**valid_paths)

    def test_properties(self, valid_model: MusicBeePaths, valid_paths: dict[str, str]):
        assert valid_model.win == PureWindowsPath(valid_paths["win"])
        assert valid_model.lin == PurePosixPath(valid_paths["lin"])
        assert valid_model.mac == PurePosixPath(valid_paths["mac"])

        assert valid_model.paths == Path(valid_paths[str(valid_model._platform_key)])
        assert all(path != valid_model.paths for path in valid_model.others)

    def test_get_paths_fails(self, invalid_paths: dict[str, str]):
        with pytest.raises(ParserError, match="No MusicBee library found"):
            MusicBeePaths(**invalid_paths)

        invalid_paths.pop(str(LocalLibraryPathsParser._platform_key))
        with pytest.raises(ParserError, match="No valid paths found for the current platform"):
            MusicBeePaths(**invalid_paths)


class TestLocalLibrary:

    # noinspection PyUnresolvedReferences,PyProtectedMember
    @pytest.fixture
    def paths_map(self, tmp_path: Path) -> dict[str, dict[str, Any]]:
        paths_map = {
            "local": TestLocalLibraryPaths.get_valid_paths(tmp_path),
            "musicbee": TestMusicBeePaths.get_valid_paths(tmp_path),
        }
        assert paths_map.keys() == LocalLibraryConfig._type_map.default.keys() == LOCAL_LIBRARY_TYPES
        return paths_map

    # noinspection PyUnresolvedReferences,PyProtectedMember
    @pytest.fixture
    def paths_type_map(self) -> dict[str, type[LocalLibraryPathsParser]]:
        type_map = {
            "local": LocalLibraryPaths,
            "musicbee": MusicBeePaths,
        }
        assert type_map.keys() == LocalLibraryConfig._type_map.default.keys() == LOCAL_LIBRARY_TYPES
        return type_map

    @pytest.fixture(params=LOCAL_LIBRARY_TYPES)
    def kind(self, request) -> str:
        return request.param

    @pytest.fixture
    def library_paths(self, kind: str, paths_map: dict[str, dict[str, Any]]):
        return paths_map[kind]

    @pytest.fixture
    def library_paths_type(self, kind: str, paths_type_map: dict[str, type[LocalLibraryPathsParser]]):
        return paths_type_map[kind]

    @pytest.fixture
    def library_model(
            self, library_paths: dict[str, Any], library_paths_model: LocalLibraryPathsParser
    ) -> LocalLibraryConfig:
        return LocalLibraryConfig[library_paths_model.__class__](
            name=random_str(), type=library_paths_model.source, paths={"library": library_paths}
        )

    @pytest.fixture
    def paths_model(
            self, kind: str, library_paths: dict[str, Any], library_paths_type: type[LocalLibraryPathsParser]
    ) -> LocalPaths:
        return LocalPaths[library_paths_type](library=library_paths)

    @pytest.fixture
    def library_paths_model(
            self, kind: str, library_paths: dict[str, Any], library_paths_type: type[LocalLibraryPathsParser]
    ) -> LocalPaths:
        return library_paths_type(**library_paths)

    def test_updates_map_with_other_platform_paths(self, paths_model: LocalPaths, library_paths: dict[str, Any]):
        assert len(paths_model.map) >= len(library_paths) - 1

        expected_path = next(iter(to_collection(library_paths[str(LocalLibraryPathsParser._platform_key)])))
        library_paths = [
            path for key, paths in library_paths.items() for path in to_collection(paths)
            if key != str(LocalLibraryPathsParser._platform_key)
        ]
        for path in library_paths:
            assert paths_model.map[path] == expected_path

    def test_assigns_library_paths(self, library_model: LocalLibraryConfig, library_paths_model: LocalLibraryPathsParser):
        assert library_model.paths.library == library_paths_model.paths

    def test_assigns_type_from_paths_parser(self, paths_model: LocalPaths, library_paths_model: LocalLibraryPathsParser):
        model = LocalLibraryConfig(name="name", paths=paths_model)
        assert model.type == library_paths_model.source

        with pytest.raises(ValidationError):  # library is not a paths parser, fails to assign type from parser
            LocalLibraryConfig(name="name", paths=LocalPaths(library=library_paths_model.paths))

    def test_determine_library_type_from_config(
            self, kind: str, library_paths: dict[str, Any], library_paths_model: LocalLibraryPathsParser
    ):
        model: LocalLibraryConfig = LocalLibraryConfig.create_and_determine_library_type(
            dict(name=kind, type=kind, paths={"library": library_paths})
        )
        # just check the paths assigned to LocalLibrary model equal the paths for the expected LocalPaths model
        assert model.paths.library == library_paths_model.paths


class TestRemoteLibrary:
    @pytest.fixture
    def api_model(self) -> APIConfig:
        return SpotifyAPIConfig(
            client_id="",
            client_secret="",
        )

    def test_assigns_type_from_api_model(self, api_model: APIConfig):
        model = RemoteLibraryConfig(name="name", api=api_model)
        assert model.type == api_model.source


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
        with pytest.raises(ParserError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries)
        with pytest.raises(ParserError, match=match):
            LibrariesConfig(local=local_libraries[0], remote=remote_libraries)
        with pytest.raises(ParserError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries[0])

    def test_fails_when_target_given_is_invalid(
            self, local_libraries: list[LocalLibraryConfig], remote_libraries: list[RemoteLibraryConfig]
    ):
        match = "target does not correspond to any configured"
        target = LibraryTarget(local="i am not a valid target", remote="I am also not a valid target")
        with pytest.raises(ParserError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries, target=target)

        valid_local_name = choice([lib.name for lib in local_libraries])
        target = LibraryTarget(local=valid_local_name, remote="invalid name")
        with pytest.raises(ParserError, match=match):
            LibrariesConfig(local=local_libraries, remote=remote_libraries, target=target)

        valid_remote_name = choice([lib.name for lib in remote_libraries])
        target = LibraryTarget(local="invalid name", remote=valid_remote_name)
        with pytest.raises(ParserError, match=match):
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
