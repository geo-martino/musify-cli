import asyncio
import logging.config
from pathlib import Path
from typing import Any

import pytest
import yaml
from aiorequestful.request import RequestHandler
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
