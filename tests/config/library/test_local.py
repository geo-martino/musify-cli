from collections.abc import Collection
from copy import deepcopy
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import Any

import pytest
from musify.libraries.local.library import MusicBee
from musify.utils import to_collection
from pydantic import ValidationError

from musify_cli.config.library.local import LOCAL_LIBRARY_TYPES, LocalLibraryPathsParser, LocalPaths, \
    LocalLibraryPaths, MusicBeePaths, LocalLibraryConfig
from utils import random_str


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
        with pytest.raises(ValidationError, match="are not valid directories"):
            LocalLibraryPaths(**invalid_paths)

        invalid_paths.pop(str(LocalLibraryPathsParser._platform_key))
        with pytest.raises(ValidationError, match="No valid paths found for the current platform"):
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
        with pytest.raises(ValidationError, match="No MusicBee library found"):
            MusicBeePaths(**invalid_paths)

        invalid_paths.pop(str(LocalLibraryPathsParser._platform_key))
        with pytest.raises(ValidationError, match="No valid paths found for the current platform"):
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

    def test_assigns_library_paths(
            self, library_model: LocalLibraryConfig, library_paths_model: LocalLibraryPathsParser
    ):
        assert library_model.paths.library == library_paths_model.paths

    def test_assigns_type_from_paths_parser(
            self, paths_model: LocalPaths, library_paths_model: LocalLibraryPathsParser
    ):
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
