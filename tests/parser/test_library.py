from argparse import Namespace
from os.path import join
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from musify_cli.exception import ParserError
from musify_cli.parser import LIBRARY_TYPES
# noinspection PyProtectedMember
from musify_cli.parser._library import LIBRARY_PARSER, LocalLibraryPaths, MusicBeePaths, library_sub_map
from tests.parser.utils import path_library_config, assert_local_parse, assert_musicbee_parse, assert_spotify_parse


# TODO: add test/assertions for PathStemMapper.
#  Should also include other platform re-mappings from the 'library' paths key

def test_all_libraries_supported():
    assert len(library_sub_map) == len(LIBRARY_TYPES)
    assert all(kind.lower() in LIBRARY_TYPES for kind in library_sub_map)


def test_local_library_paths_parser():
    config = "i/am/a/path"
    assert LocalLibraryPaths.parse_config(config) == (config,)

    config = [config, "i/am/also/a/path"]
    assert LocalLibraryPaths.parse_config(config) == config

    config = dict(win=(r"C:\windows\path",), lin=["/linux/path"], mac={"/mac/path"})
    platform_key = str(LocalLibraryPaths._platform_key)
    assert LocalLibraryPaths.parse_config(config) == tuple(config[platform_key])

    config.pop(platform_key)
    with pytest.raises(ParserError):
        LocalLibraryPaths.parse_config(config)


def test_musicbee_paths_parser():
    config = "i/am/a/path"
    assert MusicBeePaths.parse_config(config) == config

    config = ["i/am/also/a/path", config]
    assert MusicBeePaths.parse_config(config) == config[0]

    config = dict(win=(r"C:\windows\path",), lin=["/linux/path"], mac={"/mac/path"})
    platform_key = str(LocalLibraryPaths._platform_key)
    assert MusicBeePaths.parse_config(config) == config[platform_key][0]

    config.pop(platform_key)
    with pytest.raises(ParserError):
        MusicBeePaths.parse_config(config)


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


def test_local_parser(tmp_path: Path):
    def _extend_input(config: dict[str, Any]) -> None:
        config["paths"]["library"] = str(tmp_path)
        config["paths"]["playlists"] = str(tmp_path)

    parsed = parse_library(name="local", extend_input=_extend_input)
    assert_local_parse(parsed, library_path=tmp_path)


def test_musicbee_parser(tmp_path: Path):
    def _extend_input(config: dict[str, Any]) -> None:
        config["paths"]["library"] = str(tmp_path)

    parsed = parse_library(name="musicbee", extend_input=_extend_input)
    assert_musicbee_parse(parsed, library_path=tmp_path)


def test_spotify_parser(tmp_path: Path):
    token_path = join(str(tmp_path), "token.json")

    def _extend_input(config: dict[str, Any]) -> None:
        config["api"]["token_path"] = token_path

    parsed = parse_library(name="spotify", extend_input=_extend_input)
    assert_spotify_parse(parsed, token_path=token_path)
