import logging.config
import re
from os.path import join, dirname, exists
from typing import Any

import pytest
import yaml
from aioresponses import aioresponses

from musify.libraries.remote.spotify.processors import SpotifyDataWrangler
from musify.log.logger import MusifyLogger
from musify_cli import MODULE_ROOT


# noinspection PyUnusedLocal
@pytest.hookimpl
def pytest_configure(config: pytest.Config):
    """Loads logging config"""
    config_file = join(dirname(dirname(__file__)), "logging.yml")
    if not exists(config_file):
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
def requests_mock(spotify_wrangler: SpotifyDataWrangler) -> aioresponses:
    with aioresponses() as m:
        m.get(re.compile(spotify_wrangler.url_api), payload={})
        yield m
