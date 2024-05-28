from argparse import Namespace
from datetime import timedelta
from pathlib import Path, PurePath

import jsonargparse
from musify.libraries.local.track.field import LocalTrackField

from tests.utils import path_resources

path_core_config = path_resources.joinpath("test_config.yml")
path_library_config = path_resources.joinpath("test_libraries.yml")


def assert_local_parse(parsed: Namespace, library_path: str | Path = Path()) -> None:
    """Check the arguments parsed for the 'local' named library."""
    assert all(isinstance(path, PurePath) for path in parsed.paths.library.paths)
    assert tuple(map(str, parsed.paths.library.paths)) == (str(library_path),)

    assert isinstance(parsed.paths.playlists, jsonargparse.Path)
    assert str(parsed.paths.playlists) == str(library_path)

    assert parsed.paths.map == {
        "/different/folder": "/path/to/library",
        "/another/path": "/path/to/library"
    }

    assert parsed.updater.tags == (LocalTrackField.TITLE, LocalTrackField.ARTIST, LocalTrackField.ALBUM)
    assert not parsed.updater.replace

    playlist_names = ["cool playlist 1", "awesome playlist", "terrible playlist", "other"]
    assert parsed.playlists.filter(playlist_names) == ["cool playlist 1", "awesome playlist"]


def assert_musicbee_parse(parsed: Namespace, library_path: str | Path = Path()) -> None:
    """Check the arguments parsed for the 'musicbee' named library."""
    assert isinstance(parsed.paths.library.paths, PurePath)
    assert str(parsed.paths.library.paths) == str(library_path)

    assert parsed.paths.map == {"../": "/path/to/library"}

    assert parsed.updater.tags == (LocalTrackField.TITLE,)
    assert parsed.updater.replace

    playlist_names = ["cool playlist 1", "awesome playlist", "terrible playlist", "other"]
    assert parsed.playlists.filter(playlist_names) == ["cool playlist 1", "awesome playlist"]


def assert_spotify_parse(parsed: Namespace, token_path: Path | None = None) -> None:
    """Check the arguments parsed for the 'spotify' named library."""
    assert parsed.api.client_id == "<CLIENT_ID>"
    assert parsed.api.client_secret == "<CLIENT_SECRET>"
    assert parsed.api.scopes == ["user-library-read", "user-follow-read"]

    assert parsed.api.cache.type == "sqlite"
    assert parsed.api.cache.db == "cache_db"
    assert parsed.api.cache.expire_after == timedelta(weeks=2)

    print(type(parsed.api.token_path), type(token_path))
    if token_path is not None:
        assert isinstance(parsed.api.token_path, jsonargparse.Path)
        assert Path(parsed.api.token_path) == token_path

    playlist_names = ["cool playlist", "awesome playlist", "terrible playlist", "other"]
    assert parsed.playlists.filter(playlist_names) == ["cool playlist"]

    assert parsed.playlists.sync.kind == "sync"
    assert not parsed.playlists.sync.reload
    assert parsed.playlists.sync.filter == {
        "artist": ("bad artist", "nonce"),
        "album": ("unliked album",),
    }

    assert parsed.check.interval == 200
    assert parsed.check.allow_karaoke
