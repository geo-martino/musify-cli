from argparse import Namespace
from collections.abc import Collection, Callable
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any

import pytest
import yaml

from musify_cli.exception import ParserError
from musify_cli.parser import LIBRARY_TYPES
# noinspection PyProtectedMember
from musify_cli.parser._library import LIBRARY_PARSER, LocalLibraryPaths, MusicBeePaths, library_sub_map
from tests.parser.utils import path_library_config
from tests.parser.utils import assert_local_parse, assert_musicbee_parse, assert_spotify_parse


@pytest.fixture
def library_paths_platform_map() -> dict[str, Collection[PurePath]]:
    """PurePaths test map for various platforms supported by the paths parser."""
    return dict(
        win=(PureWindowsPath(r"C:\windows\path"),),
        lin=[PurePosixPath("/linux/path")],
        mac={PurePosixPath("/mac/path")}
    )


def test_all_libraries_supported():
    assert len(library_sub_map) == len(LIBRARY_TYPES)
    assert all(kind.lower() in LIBRARY_TYPES for kind in library_sub_map)


def test_local_library_paths_parser(library_paths_platform_map: dict[str, Collection[PurePath]]):
    config = Path("i/am/a/path")
    assert LocalLibraryPaths.parse_config(config).paths == (config,)

    config = [config, Path("i/am/also/a/path")]
    assert LocalLibraryPaths.parse_config(config).paths == tuple(config)

    config = library_paths_platform_map
    platform_key = str(LocalLibraryPaths._platform_key)
    assert LocalLibraryPaths.parse_config(config).paths == tuple(config[platform_key])

    config.pop(platform_key)
    parsed = LocalLibraryPaths.parse_config(config)
    with pytest.raises(ParserError):
        LocalLibraryPaths.parse_config(parsed)


def test_musicbee_paths_parser(library_paths_platform_map: dict[str, Collection[PurePath]]):
    config = Path("i/am/a/path")
    assert MusicBeePaths.parse_config(config).paths == config

    config = [Path("i/am/also/a/path"), config]
    assert MusicBeePaths.parse_config(config).paths == config[0]

    config = library_paths_platform_map
    platform_key = str(LocalLibraryPaths._platform_key)
    assert MusicBeePaths.parse_config(config).paths == next(iter(config[platform_key]))

    config.pop(platform_key)
    parsed = MusicBeePaths.parse_config(config)
    with pytest.raises(ParserError):
        MusicBeePaths.parse_config(parsed)


def parse_library(name: str, extend_input: Callable[[dict[str, Any]], None] = lambda x: x) -> Namespace:
    """
    Parse the library from the library config file and run basic assertions on it.

    :return: The library Namespace as given by the type of the given ``name``.
    """
    with open(path_library_config, "r") as file:
        config: dict[str, Any] = yaml.full_load(file)

    config = {"name": name} | config[name]
    extend_input(config[name])

    parsed = LIBRARY_PARSER.parse_object(config)
    assert parsed.name == name
    assert parsed.type == name

    return parsed.get(parsed.type)


def test_local_parser(library_paths_platform_map: dict[str, Collection[PurePath]], tmp_path: Path):
    def _extend_input(config: dict[str, Any]) -> None:
        config["paths"]["library"] = tmp_path
        config["paths"]["playlists"] = tmp_path

    parsed = parse_library(name="local", extend_input=_extend_input)
    assert_local_parse(parsed, library_path=tmp_path)

    def _extend_input(config: dict[str, Any]) -> None:
        config["paths"]["library"] = library_paths_platform_map

    parsed = parse_library(name="local", extend_input=_extend_input)

    assert parsed.paths.library == LocalLibraryPaths(**{k: tuple(v) for k, v in library_paths_platform_map.items()})
    library_path = next(iter(parsed.paths.library.paths))
    assert parsed.paths.map == {
        "/different/folder": "/path/to/library",
        "/another/path": "/path/to/library"
    } | {str(path): str(library_path) for path in parsed.paths.library.others}


def test_musicbee_parser(library_paths_platform_map: dict[str, Collection[PurePath]], tmp_path: Path):
    def _extend_input(config: dict[str, Any]) -> None:
        config["paths"]["library"] = tmp_path

    parsed = parse_library(name="musicbee", extend_input=_extend_input)
    assert_musicbee_parse(parsed, library_path=tmp_path)

    library_paths_platform_map = {k: next(iter(v)) for k, v in library_paths_platform_map.items()}

    def _extend_input(config: dict[str, Any]) -> None:
        config["paths"]["library"] = {k: str(v) for k, v in library_paths_platform_map.items()}

    parsed = parse_library(name="musicbee", extend_input=_extend_input)

    assert parsed.paths.library == MusicBeePaths(**library_paths_platform_map)
    assert parsed.paths.map == {
        "../": "/path/to/library",
    } | {str(path): str(parsed.paths.library.paths) for path in parsed.paths.library.others}


def test_spotify_parser(tmp_path: Path):
    token_file_path = tmp_path.joinpath("token").with_suffix(".json")

    def _extend_input(config: dict[str, Any]) -> None:
        config["api"]["token_file_path"] = token_file_path

    parsed = parse_library(name="spotify", extend_input=_extend_input)
    assert_spotify_parse(parsed, token_file_path=token_file_path)
