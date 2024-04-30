from argparse import Namespace
from os.path import join
from pathlib import Path

from musify.libraries.local.track.field import LocalTrackField
from tests.utils import path_resources

path_core_config = join(path_resources, "test_config.yml")
path_library_config = join(path_resources, "test_libraries.yml")


def assert_local_parse(parsed: Namespace, library_path: str | Path = ".") -> None:
    """Check the arguments parsed for the 'local' named library."""
    assert parsed.paths.library.paths == (str(library_path),)
    assert parsed.paths.playlists == str(library_path)
    assert parsed.paths.map == {
        "/different/folder": "/path/to/library",
        "/another/path": "/path/to/library"
    }

    assert parsed.updater.tags == (LocalTrackField.TITLE, LocalTrackField.ARTIST, LocalTrackField.ALBUM)
    assert not parsed.updater.replace

    playlist_names = ["cool playlist 1", "awesome playlist", "terrible playlist", "other"]
    assert parsed.playlists.filter(playlist_names) == ["cool playlist 1", "awesome playlist"]


def assert_musicbee_parse(parsed: Namespace, library_path: str | Path = ".") -> None:
    """Check the arguments parsed for the 'musicbee' named library."""
    assert parsed.paths.library.paths == str(library_path)
    assert parsed.paths.map == {"../": "/path/to/library"}

    assert parsed.updater.tags == (LocalTrackField.TITLE,)
    assert parsed.updater.replace

    playlist_names = ["cool playlist 1", "awesome playlist", "terrible playlist", "other"]
    assert parsed.playlists.filter(playlist_names) == ["cool playlist 1", "awesome playlist"]


def assert_spotify_parse(parsed: Namespace, token_path: str | None = None) -> None:
    """Check the arguments parsed for the 'spotify' named library."""
    assert parsed.api.client_id == "<CLIENT_ID>"
    assert parsed.api.client_secret == "<CLIENT_SECRET>"
    assert parsed.api.token_path == token_path
    assert parsed.api.cache_path == "cache"
    assert parsed.api.scopes == ["user-library-read", "user-follow-read"]
    assert not parsed.api.use_cache

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
