from pathlib import Path

import pytest
from faker import Faker
from mytunes.core.cursors import UrlCursor
from mytunes.core.playlist import RemotePlaylist
from mytunes.core.user import RemoteUser
from mytunes.local.playlist import LocalPlaylist
from mytunes.local.playlist import M3U
from yarl import URL

from remote import SimpleURI


@pytest.fixture
def local_playlists(faker: Faker) -> list[LocalPlaylist]:
    return [
        M3U(name=faker.sentence().rstrip("."), path=Path(faker.file_path()))
        for _ in range(faker.random_int(10, 30))
    ]


@pytest.fixture
def remote_playlists(faker: Faker) -> list[RemotePlaylist]:
    return [
        RemotePlaylist(
            name=faker.sentence().rstrip("."),
            uri=SimpleURI.create_random(RemotePlaylist.type),
            owner=RemoteUser(name=faker.name(), uri=SimpleURI.create_random(RemoteUser.type)),
            cursor=UrlCursor(url=URL(faker.url())),
        )
        for _ in range(faker.random_int(10, 30))
    ]




