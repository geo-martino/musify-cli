from datetime import datetime
from pathlib import Path
from typing import Any

import jsonargparse
import pytest
import yaml
from musify.field import TagFields
from musify.libraries.local.track.field import LocalTrackField

from musify_cli.exception import ParserError
from musify_cli.parser import LoadTypesLocal, LoadTypesRemote, EnrichTypesRemote
# noinspection PyProtectedMember
from musify_cli.parser._core import CORE_PARSER, append_parent_folder
# noinspection PyProtectedMember
from musify_cli.parser._core import parse_local_library_config, parse_remote_library_config
from tests.parser.utils import path_core_config, path_library_config
from tests.parser.utils import assert_local_parse, assert_musicbee_parse, assert_spotify_parse
from tests.utils import path_logging_config


def test_append_parent_folder(tmp_path: Path):
    relative_path = "i_am_a_relative_path.txt"
    absolute_path = append_parent_folder(relative_path, tmp_path)
    assert absolute_path == tmp_path.joinpath(relative_path)
    assert append_parent_folder(absolute_path, tmp_path.joinpath("folder1", "folder2")) == absolute_path


def test_parse_library_config_fails(tmp_path: Path):
    with pytest.raises(ParserError):  # key to library config given, but no config given
        parse_local_library_config(lib="local")

    with pytest.raises(ParserError):  # key to library config given which doesn't exist in config file
        parse_local_library_config(lib="key does not exist", config_path=path_library_config)


# noinspection PyTestUnpassedFixture
def test_parse_library_config(tmp_path: Path):
    parsed = parse_local_library_config(lib="local", config_path=path_library_config)
    assert_local_parse(parsed.get(parsed.type))

    with open(path_library_config, "r") as file:
        config: dict[str, Any] = yaml.full_load(file)

    parsed = parse_local_library_config({"name": "local"} | config["local"])
    assert_local_parse(parsed.get(parsed.type))

    parsed = parse_local_library_config(lib="musicbee", config_path=path_library_config)
    assert_musicbee_parse(parsed.get(parsed.type))

    parsed = parse_remote_library_config(lib="spotify", config_path=path_library_config)
    assert_spotify_parse(parsed.get(parsed.type))

    parsed = parse_remote_library_config(lib="spotify", config_path=path_library_config, output_folder=tmp_path)
    parsed_library = parsed.get(parsed.type)
    assert parsed_library.api.token_file_path is None
    assert parsed_library.api.cache.db == str(tmp_path.joinpath("cache_db"))


def test_core(tmp_path: Path):
    with open(path_core_config, "r") as file:
        config: dict[str, Any] = yaml.full_load(file)

    config["output"] = tmp_path
    config["logging"]["config_path"] = path_logging_config
    config["libraries"]["config_path"] = path_library_config

    parsed = CORE_PARSER.parse_object(config)

    assert isinstance(parsed.output, jsonargparse.Path)
    assert str(parsed.output) == str(tmp_path)
    assert parsed.execute

    assert isinstance(parsed.logging.config_path, jsonargparse.Path)
    assert str(parsed.logging.config_path) == str(path_logging_config)
    assert parsed.logging.name == "logger"

    values = ["include me", "exclude me", "and me"]
    assert parsed.filter(values) == ["include me"]
    assert parsed.pause == "this is a test message"

    assert parsed.reload.local.types == [LoadTypesLocal.tracks]
    assert parsed.reload.remote.types == [LoadTypesRemote.saved_tracks, LoadTypesRemote.saved_albums]
    assert parsed.reload.remote.extend
    assert parsed.reload.remote.enrich.enabled
    assert parsed.reload.remote.enrich.types == [EnrichTypesRemote.tracks, EnrichTypesRemote.albums]

    assert parsed.libraries.local.name == "local"
    assert parsed.libraries.local.type == "local"
    assert parsed.libraries.remote.name == "spotify"
    assert parsed.libraries.remote.type == "spotify"

    assert parsed.backup.key == "test key"

    assert parsed.reports.playlist_differences.enabled
    values = ["a", "b", "c", 1, 2, 3, "you", "and", "me"]
    assert parsed.reports.playlist_differences.filter(values) == ["a", "b", "c"]
    assert not parsed.reports.missing_tags.enabled
    assert not parsed.reports.missing_tags.filter.ready
    assert parsed.reports.missing_tags.tags == (
        LocalTrackField.TITLE,
        LocalTrackField.ARTIST,
        LocalTrackField.ALBUM,
        LocalTrackField.TRACK_NUMBER,
        LocalTrackField.TRACK_TOTAL,
    )
    assert parsed.reports.missing_tags.match_all

    assert parsed.download.urls == [
        "https://www.google.com/search?q={}",
        "https://www.youtube.com/results?search_query={}",
    ]
    assert parsed.download.fields == (TagFields.ARTIST, TagFields.ALBUM)
    assert parsed.download.interval == 1

    assert parsed.new_music.name == "New Music - 2023"
    assert parsed.new_music.start == datetime(2023, 1, 1).date()
    assert parsed.new_music.end == datetime(2023, 12, 31).date()

    # just check it can be dumped without failing
    CORE_PARSER.dump(parsed)
