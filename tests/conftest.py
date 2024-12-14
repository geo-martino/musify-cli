import asyncio
import logging.config
from pathlib import Path
from typing import Any

import pytest
import yaml
from aiorequestful.request import RequestHandler
from musify.libraries.local.library import MusicBee
from musify.libraries.local.track import LocalTrack
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from musify.logger import MusifyLogger
from pytest_mock import MockerFixture

from musify_cli import MODULE_ROOT
from tests.utils import random_track, random_tracks


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# noinspection PyUnusedLocal
@pytest.hookimpl
def pytest_configure(config: pytest.Config):
    """Loads logging config"""
    config_file = Path(__file__).parent.with_stem("logging").with_suffix(".yml")
    if not config_file.is_file():
        return

    with open(config_file, "r", encoding="utf-8") as file:
        log_config = yaml.full_load(file)

    log_config.pop("compact", False)
    MusifyLogger.disable_bars = True
    MusifyLogger.compact = True

    def remove_file_handler(c: dict[str, Any]) -> None:
        """Remove all config for file handlers"""
        for k, v in c.items():
            if k == "handlers" and isinstance(v, list) and "file" in v:
                v.pop(v.index("file"))
            elif k == "handlers" and isinstance(v, dict) and "file" in v:
                v.pop("file")
            elif isinstance(v, dict):
                remove_file_handler(v)

    remove_file_handler(log_config)

    for formatter in log_config["formatters"].values():  # ensure ANSI colour codes in format are recognised
        formatter["format"] = formatter["format"].replace(r"\33", "\33")

    log_config["loggers"][MODULE_ROOT] = log_config["loggers"]["test"]
    logging.config.dictConfig(log_config)


@pytest.fixture(scope="session")
def spotify_wrangler() -> SpotifyDataWrangler:
    """Yields a :py:class:`SpotifyDataWrangler` for testing Spotify data wrangling"""
    return SpotifyDataWrangler()


@pytest.fixture(autouse=True)
async def requests_mock(mocker: MockerFixture) -> None:
    mocker.patch.object(RequestHandler, "request", return_value={})
    yield
    mocker.stopall()


@pytest.fixture
def track() -> LocalTrack:
    return random_track()


@pytest.fixture
def tracks() -> list[LocalTrack]:
    return random_tracks()


@pytest.fixture
def library_folders(tmp_path: Path) -> list[Path]:
    """The library folders to use when generating the MusicBee settings file."""
    library_folders = [tmp_path.joinpath("library_1"), tmp_path.joinpath("library_2")]
    for path in library_folders:
        path.mkdir(parents=True, exist_ok=True)
    return library_folders


# noinspection PyMethodOverriding
@pytest.fixture
def musicbee_folder(tmp_path: Path, library_folders: list[Path]) -> Path:
    musicbee_folder = tmp_path.joinpath("library")
    musicbee_folder.mkdir(parents=True, exist_ok=True)

    playlists_folder = musicbee_folder.joinpath(MusicBee.playlists_path)
    playlists_folder.mkdir(parents=True, exist_ok=True)

    xml_library = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<!DOCTYPE plist PUBLIC \"-//Apple Computer//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">",
        "<plist version=\"1.0\">",
        "<dict>",
        "<key>Major Version</key><integer>3</integer>",
        "<key>Minor Version</key><integer>5</integer>",
        "<key>Application Version</key><string>3.5.8447.35892</string>",
        f"<key>Music Folder</key><string>file://localhost/{musicbee_folder}</string>",
        "<key>Library Persistent ID</key><string>3D76B2A6FD362901</string>",
        "<key>Tracks</key>",
        "<dict/>",
        "<key>Playlists</key>",
        "<array/>",
        "</dict>",
        "</plist>",
    )
    with open(musicbee_folder.joinpath(MusicBee.xml_library_path), "w") as f:
        f.write("\n".join(xml_library))

    # noinspection SpellCheckingInspection
    xml_settings = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>",
        "<ApplicationSettings xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
        "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\">",
        f"<Path>{musicbee_folder}</Path>",
        "<OrganisationMonitoredFolders>",
        f" <string>{library_folders[0]}</string>",
        f" <string>{library_folders[1]}</string>",
        "</OrganisationMonitoredFolders>",
        "</ApplicationSettings>",
    )
    with open(musicbee_folder.joinpath(MusicBee.xml_settings_path), "w") as f:
        f.write("\n".join(xml_settings))

    return musicbee_folder
