import pytest

from musify.libraries.remote.spotify.processors import SpotifyDataWrangler


@pytest.fixture(scope="session")
def spotify_wrangler() -> SpotifyDataWrangler:
    """Yields a :py:class:`SpotifyDataWrangler` for testing Spotify data wrangling"""
    return SpotifyDataWrangler()
