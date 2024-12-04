from abc import ABCMeta
from datetime import datetime
from random import choice, randrange
from typing import Any

from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.library import RemoteLibrary
from musify.libraries.remote.core.object import SyncResultRemotePlaylist, RemoteTrack, \
    RemotePlaylist, RemoteAlbum, RemoteArtist
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.factory import SpotifyObjectFactory
from musify.libraries.remote.spotify.library import SpotifyLibrary
from musify.libraries.remote.spotify.object import SpotifyTrack, SpotifyPlaylist, SpotifyAlbum, SpotifyArtist

from tests.mocks.core import LibraryMock
from musify_cli.config.library.types import LoadTypesRemote
from utils import random_str


class RemoteTrackMock(RemoteTrack, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        kwargs.pop("skip_checks", None)
        super().__init__(*args, **kwargs, skip_checks=True)

        self._name = random_str()

    def _check_type(self) -> None:
        pass

    @property
    def name(self):
        return self._name

    @property
    def uri(self):
        return self._name


class RemotePlaylistMock(RemotePlaylist, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        kwargs.pop("skip_checks", None)
        super().__init__(*args, **kwargs, skip_checks=True)

        self._name = random_str()

        self.sync_args: dict[str, Any] = {}

    def _check_type(self) -> None:
        pass

    @property
    def name(self):
        # noinspection PyBroadException
        try:
            return super().name
        except Exception:
            return self._name

    @property
    def uri(self):
        # noinspection PyBroadException
        try:
            return super().uri
        except Exception:
            return self._name

    async def sync(self, *args, **kwargs) -> SyncResultRemotePlaylist:
        self.sync_args["_args"] = args
        self.sync_args |= kwargs

        return SyncResultRemotePlaylist(
            start=randrange(0, 10),
            added=randrange(0, 10),
            removed=randrange(0, 10),
            unchanged=randrange(0, 10),
            difference=randrange(0, 10),
            final=randrange(0, 10),
        )


class RemoteAlbumMock(RemoteAlbum, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        kwargs.pop("skip_checks", None)
        super().__init__(*args, **kwargs, skip_checks=True)

        self._year = datetime.now().year
        self._month = choice([None, randrange(1, 12)])
        self._day = choice([None, randrange(1, 28)]) if self._month is not None else None
        if self._month is not None and self._day is not None:
            self._date = datetime(self._year, self._month, self._day).date()
        else:
            self._date = None

    def _check_type(self) -> None:
        pass

    @property
    def date(self):
        return self._date

    @property
    def year(self):
        return self._year

    @property
    def month(self):
        return self._month

    @property
    def day(self):
        return self._day


class RemoteArtistMock(RemoteArtist, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        kwargs.pop("skip_checks", None)
        super().__init__(*args, **kwargs, skip_checks=True)

    def _check_type(self) -> None:
        pass


class RemoteAPIMock(RemoteAPI, metaclass=ABCMeta):
    pass


class RemoteLibraryMock(LibraryMock, RemoteLibrary[
    RemoteAPIMock, RemotePlaylistMock, RemoteTrackMock, RemoteAlbumMock, RemoteArtistMock
], metaclass=ABCMeta):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.load_calls: list[str] = []
        self.enrich_tracks_args: dict[str, Any] = {}
        self.enrich_saved_albums_args: dict[str, Any] = {}
        self.enrich_saved_artists_args: dict[str, Any] = {}
        self.sync_args: dict[str, Any] = {}

    def reset(self):
        """Reset all mock attributes"""
        self.load_calls.clear()
        self.enrich_tracks_args.clear()
        self.enrich_saved_albums_args.clear()
        self.enrich_saved_artists_args.clear()
        self.sync_args.clear()

    async def load(self):
        self.load_calls.append("ALL")

    async def load_tracks(self):
        self.load_calls.append(LoadTypesRemote.SAVED_TRACKS.name)

    async def load_playlists(self):
        self.load_calls.append(LoadTypesRemote.PLAYLISTS.name)

    async def load_saved_albums(self):
        self.load_calls.append(LoadTypesRemote.SAVED_ALBUMS.name)

    async def load_saved_artists(self):
        self.load_calls.append(LoadTypesRemote.SAVED_ARTISTS.name)

    async def sync(self, *args, **kwargs) -> dict[str, SyncResultRemotePlaylist]:
        self.sync_args["_args"] = args
        self.sync_args |= kwargs
        return {}


###########################################################################
## Spotify
###########################################################################
class SpotifyTrackMock(RemoteTrackMock, SpotifyTrack):
    pass


class SpotifyPlaylistMock(RemotePlaylistMock, SpotifyPlaylist):
    pass


class SpotifyAlbumMock(RemoteAlbumMock, SpotifyAlbum):
    pass


class SpotifyArtistMock(RemoteArtistMock, SpotifyArtist):
    pass


class SpotifyAPIMock(RemoteAPIMock, SpotifyAPI):
    async def create_playlist(
            self, name: str, public: bool = True, collaborative: bool = False, *_, **__
    ) -> dict[str, Any]:
        return {
            "name": name
        }


class SpotifyLibraryMock(RemoteLibraryMock, SpotifyLibrary):
    def __init__(self, *args, **kwargs):
        if "api" not in kwargs:
            kwargs["api"] = SpotifyAPIMock()
        super().__init__(*args, **kwargs)

        self._factory = SpotifyObjectFactory(
            api=self.api,
            playlist=SpotifyPlaylistMock,
            track=SpotifyTrackMock,
            album=SpotifyAlbumMock,
            artist=SpotifyArtistMock,
        )

    async def enrich_tracks(self, *args, **kwargs) -> None:
        self.enrich_tracks_args["_args"] = args
        self.enrich_tracks_args |= kwargs

    async def enrich_saved_albums(self) -> None:
        self.enrich_saved_albums_args = {}

    async def enrich_saved_artists(self, *args, **kwargs) -> None:
        self.enrich_saved_artists_args["_args"] = args
        self.enrich_saved_artists_args |= kwargs
