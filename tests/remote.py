import re
from collections.abc import Mapping
from random import choice
from typing import ClassVar, final, Self, Any
from unittest.mock import Mock, patch, MagicMock

from aiorequestful.auth import Authoriser
from faker import Faker
from mytunes.annotation import ResourceModel
from mytunes.core.album import Album
from mytunes.core.api import RemoteAPI, RemoteAuthoriser, HasLibraryEndpoints
from mytunes.core.api.playlist import HasPlaylistEndpoints, PlaylistLibraryEndpoints, PlaylistReadWriteEndpoints
from mytunes.core.api.search import HasSearchEndpoints, SearchEndpoints
from mytunes.core.artist import Artist
from mytunes.core.library import Library, RemoteMutableLibrary
from mytunes.core.playlist import Playlist, RemotePlaylist
from mytunes.core.properties.uri import URI
from mytunes.core.track import Track, RemoteTrack
from mytunes.core.user import RemoteUser
from yarl import URL

from mytunes_cli.state import GlobalState


@final
class SimpleURI(URI):
    __final__ = True
    _source = "remote"

    @property
    def source(self) -> str:
        return self.root.split(":")[0]

    @property
    def type(self) -> str:
        return self.root.split(":")[1]

    @property
    def id(self) -> str:
        return self.root.split(":")[2]

    @classmethod
    def create_random(cls, kind: str | None = None) -> Self:
        if not kind:
            kind = choice((Track.type, Album.type, Artist.type, Playlist.type))
        value = Faker().pystr()
        return cls.from_id(value=value, kind=kind)

    @classmethod
    def create_unavailable(cls, kind: str) -> Self:
        return cls.from_id(value=cls._unavailable_id, kind=kind)

    @classmethod
    def from_id[T](cls, value: T, kind: str) -> T | Self:
        uri = ":".join((cls._source, kind, str(value)))
        return cls(uri)

    @property
    def api_url(self) -> URL:
        return URL.build(scheme="https", host="api.example.com", path=f"/{self.type}/{self.id}")

    @classmethod
    def from_api_url[T](cls, value: T) -> T | str:
        return cls.from_public_url(value)

    @property
    def public_url(self) -> URL:
        return URL.build(scheme="https", host="example.com", path=f"/{self.type}/{self.id}")

    @classmethod
    def from_public_url[T](cls, value: T) -> T | str:
        if isinstance(value, str) and re.match(r"^https://(api.)?example\.com", value):
            value = URL(value)
        if not isinstance(value, URL):
            return value

        return ":".join((cls._source, *value.path.lstrip("/").split("/")[-2:]))


class MockRemoteAuthoriser(RemoteAuthoriser[Mock]):
    source: ClassVar[str] = "remote"

    client_id: str = "test_client_id"

    @patch.multiple(
        Authoriser,
        __abstractmethods__=set(),
        authorise=MagicMock(),
    )
    def create_authoriser(self) -> Authoriser:
        # noinspection PyAbstractClass
        return Authoriser()


class MockSearchEndpoints(
    SearchEndpoints[SimpleURI, RemoteTrack, ResourceModel]
):
    _query_url = URL("https://api.example.com/search")
    _query_path = "items"
    _query_limit = 22

    def _format_query_params(self, query, types, limit=None, **kwargs) -> dict[str, Any]:
        pass

    def _format_query_from_item(self, item, **kwargs) -> dict[str, Any]:
        pass


class MockPlaylistLibraryEndpoints(
    PlaylistLibraryEndpoints[SimpleURI, RemotePlaylist, RemoteUser],
):
    pass


class MockPlaylistEndpoints(
    PlaylistReadWriteEndpoints[SimpleURI, RemotePlaylist, RemoteTrack],
    HasLibraryEndpoints[MockPlaylistLibraryEndpoints],
):
    pass


@final
class MockRemoteAPI(
    RemoteAPI[MockRemoteAuthoriser],
    HasSearchEndpoints[MockSearchEndpoints],
    HasPlaylistEndpoints[MockPlaylistEndpoints],
):
    __final__ = True
    source: ClassVar[str] = MockRemoteAuthoriser.source

    async def __aenter__(self) -> Self:
        return self


@final
class MockRemoteMutableLibrary(RemoteMutableLibrary):
    __final__ = True
    source: ClassVar[str] = MockRemoteAuthoriser.source

    api: MockRemoteAPI


# force adding the new mock library to the libraries annotation
GlobalState.model_fields["libraries"].annotation = Mapping[str, Library | MockRemoteMutableLibrary]
GlobalState.model_rebuild(force=True)
