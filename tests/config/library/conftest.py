import pytest
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.spotify.factory import SpotifyObjectFactory
from musify.processors.match import ItemMatcher

from mocks.remote import SpotifyPlaylistMock, SpotifyTrackMock, SpotifyAlbumMock, SpotifyArtistMock


@pytest.fixture
def matcher() -> ItemMatcher:
    return ItemMatcher()


@pytest.fixture
def spotify_factory() -> RemoteObjectFactory:
    return SpotifyObjectFactory(
        playlist=SpotifyPlaylistMock,
        track=SpotifyTrackMock,
        album=SpotifyAlbumMock,
        artist=SpotifyArtistMock,
    )
