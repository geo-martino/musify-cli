from abc import ABCMeta
from datetime import timedelta
from pathlib import Path

import pytest
from musify.field import TagFields
from musify.libraries.remote.core.library import RemoteLibrary
from musify.libraries.remote.spotify import SOURCE_NAME as SPOTIFY_SOURCE
from musify.libraries.remote.spotify.library import SpotifyLibrary

from mocks.remote import RemotePlaylistMock, RemoteTrackMock, RemoteLibraryMock, RemoteAlbumMock, RemoteArtistMock, \
    SpotifyLibraryMock, SpotifyPlaylistMock, SpotifyAlbumMock, SpotifyTrackMock, SpotifyArtistMock
from musify_cli.config.library.remote import RemoteLibraryConfig, SpotifyAPIConfig, APICacheConfig, \
    APIHandlerConfig, APIHandlerRetry, APIHandlerWait, RemoteItemCheckerConfig, RemoteItemDownloadConfig, \
    RemotePlaylistsConfig, RemotePlaylistsSync, SpotifyLibraryConfig
from musify_cli.config.library.types import LoadTypesRemote, EnrichTypesRemote
from musify_cli.exception import ParserError
from musify_cli.manager.library import RemoteLibraryManager
from tests.manager.library.testers import LibraryManagerTester


class RemoteLibraryManagerTester[L: RemoteLibrary, C: RemoteLibraryConfig](
    LibraryManagerTester[RemoteLibraryManager[L, C]], metaclass=ABCMeta
):

    library_mock: type[RemoteLibraryMock]
    playlist_mock: type[RemotePlaylistMock]
    track_mock: type[RemoteTrackMock]
    album_mock: type[RemoteAlbumMock]
    artist_mock: type[RemoteArtistMock]

    @pytest.fixture
    def load_types(self) -> type[LoadTypesRemote]:
        return LoadTypesRemote

    @pytest.fixture
    async def manager_mock(self, manager: RemoteLibraryManager[L, C]) -> RemoteLibraryManager[L, C]:
        """
        Replace the instantiated library from the given ``manager`` with a mocked library.
        Yields the modified ``manager`` as a pytest.fixture.
        """
        manager.config.__class__._library_cls = self.library_mock
        manager.factory.playlist = self.playlist_mock
        manager.factory.album = self.album_mock

        return manager

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_run_download_helper(self, manager_mock: RemoteLibraryManager[L, C]):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_restore_library(self, manager_mock: RemoteLibraryManager[L, C]):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_create_new_music_playlist(self, manager_mock: RemoteLibraryManager[L, C]):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_load_followed_artist_albums(self, manager_mock: RemoteLibraryManager[L, C]):
        pass  # TODO

    @pytest.mark.skip(reason="Test not yet implemented")
    def test_extend_albums(self, manager_mock: RemoteLibraryManager[L, C]):
        pass  # TODO


class TestSpotifyLibraryManager(RemoteLibraryManagerTester[SpotifyLibrary, SpotifyLibraryConfig]):

    library_mock: type[SpotifyLibraryMock] = SpotifyLibraryMock
    playlist_mock: type[SpotifyPlaylistMock] = SpotifyPlaylistMock
    track_mock: type[SpotifyTrackMock] = SpotifyTrackMock
    album_mock: type[SpotifyAlbumMock] = SpotifyAlbumMock
    artist_mock: type[SpotifyArtistMock] = SpotifyArtistMock

    @pytest.fixture
    def config(self, tmp_path: Path) -> SpotifyLibraryConfig:
        return SpotifyLibraryConfig(
            name="name",
            api=SpotifyAPIConfig(
                client_id="<CLIENT ID>",
                client_secret="<CLIENT SECRET>",
                scope=[
                    "user-library-read",
                    "user-follow-read",
                ],
                handler=APIHandlerConfig(
                    retry=APIHandlerRetry(
                        initial=2,
                        count=20,
                        factor=1.5,
                    ),
                    wait=APIHandlerWait(
                        initial=1,
                        final=3,
                        step=0.3,
                    ),
                ),
                cache=APICacheConfig(
                    type="sqlite",
                    db=str(tmp_path.joinpath("cache_db")),
                    expire_after=timedelta(days=16),
                ),
                token_file_path=tmp_path.joinpath("token.json"),
            ),
            check=RemoteItemCheckerConfig(
                interval=200,
                allow_karaoke=True,
            ),
            download=RemoteItemDownloadConfig(
                urls=[
                    "https://www.google.com/search?q={}",
                    "https://www.youtube.com/results?search_query={}",
                ],
                fields=(TagFields.ARTIST, TagFields.ALBUM),
                interval=4,
            ),
            playlists=RemotePlaylistsConfig(
                filter=["playlist 1", "playlist 2"],
                sync=RemotePlaylistsSync(
                    kind="sync",
                    reload=True,
                    filter={
                        "artist": ("bad artist", "nonce"),
                        "album": ("unliked album",),
                    },
                ),
            ),
        )

    # noinspection PyMethodOverriding
    @pytest.fixture
    async def manager(self, config: SpotifyLibraryConfig) -> RemoteLibraryManager[SpotifyLibrary, SpotifyLibraryConfig]:
        manager = RemoteLibraryManager[SpotifyLibrary, SpotifyLibraryConfig](config=config)

        authoriser = manager.api.handler.authoriser
        authoriser.response.replace({
            "access_token": "fake access token", "token_type": "Bearer", "scope": "test-read"
        })
        authoriser.tester.request = None
        authoriser.tester.response_test = None
        authoriser.tester.max_expiry = 0

        async with manager as m:
            yield m

    def test_properties(
            self, manager: RemoteLibraryManager[SpotifyLibrary, SpotifyLibraryConfig], config: SpotifyLibraryConfig
    ):
        assert manager.source == SPOTIFY_SOURCE

    async def test_enrich_all(self, manager_mock: RemoteLibraryManager[SpotifyLibrary, SpotifyLibraryConfig]):
        # noinspection PyTypeChecker
        library: SpotifyLibraryMock = manager_mock.library

        manager_mock.types_loaded = set(LoadTypesRemote.all())

        assert LoadTypesRemote.SAVED_TRACKS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        await manager_mock.enrich()

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS in manager_mock.types_enriched

        # just check each method was called
        assert library.enrich_tracks_args
        assert not library.enrich_saved_albums_args  # currently has no args
        assert library.enrich_saved_artists_args

        # should enrich all those that have been loaded only and skip those that have been enriched
        library.reset()
        await manager_mock.enrich(force=True)

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS in manager_mock.types_enriched

        # just check each method was called again
        assert library.enrich_tracks_args
        assert not library.enrich_saved_albums_args  # currently has no args
        assert library.enrich_saved_artists_args

    async def test_enrich_limited_on_load_types(
            self, manager_mock: RemoteLibraryManager[SpotifyLibrary, SpotifyLibraryConfig]
    ):
        # noinspection PyTypeChecker
        library: SpotifyLibraryMock = manager_mock.library

        manager_mock.types_loaded = {LoadTypesRemote.SAVED_ALBUMS, LoadTypesRemote.SAVED_TRACKS}

        assert LoadTypesRemote.SAVED_TRACKS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        await manager_mock.enrich(types=LoadTypesRemote.SAVED_TRACKS)

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.SAVED_TRACKS]
        assert enriched_types_track == {EnrichTypesRemote.ARTISTS, EnrichTypesRemote.ALBUMS}
        assert library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.SAVED_ALBUMS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        # should enrich all those that have been loaded only and skip those that have been enriched
        library.reset()
        await manager_mock.enrich()

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        assert not library.enrich_tracks_args

        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched
        enriched_types_album = manager_mock.types_enriched[LoadTypesRemote.SAVED_ALBUMS]
        assert not enriched_types_album
        assert not library.enrich_saved_albums_args  # currently has no args

        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        # on force, re-enriches loaded types but still doesn't try to enrich unloaded types
        library.reset()
        await manager_mock.enrich(force=True)

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        assert library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

    async def test_enrich_limited_on_enrich_types(
            self, manager_mock: RemoteLibraryManager[SpotifyLibrary, SpotifyLibraryConfig]
    ):
        # noinspection PyTypeChecker
        library: SpotifyLibraryMock = manager_mock.library

        manager_mock.types_loaded = set(LoadTypesRemote.all())

        assert LoadTypesRemote.SAVED_TRACKS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ALBUMS not in manager_mock.types_enriched
        assert LoadTypesRemote.SAVED_ARTISTS not in manager_mock.types_enriched

        await manager_mock.enrich(enrich=EnrichTypesRemote.ARTISTS)

        assert LoadTypesRemote.SAVED_TRACKS in manager_mock.types_enriched
        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.SAVED_TRACKS]
        assert enriched_types_track == {EnrichTypesRemote.ARTISTS}
        assert not library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        assert LoadTypesRemote.SAVED_ALBUMS in manager_mock.types_enriched

        assert LoadTypesRemote.SAVED_ARTISTS in manager_mock.types_enriched
        enriched_types_artist = manager_mock.types_enriched[LoadTypesRemote.SAVED_ARTISTS]
        assert not enriched_types_artist
        assert not library.enrich_saved_artists_args["tracks"]

        # should skip those that have been enriched
        library.reset()
        await manager_mock.enrich(enrich=EnrichTypesRemote.ARTISTS)

        assert not library.enrich_tracks_args
        assert not library.enrich_saved_artists_args

        # on force, re-enriches loaded types but still doesn't try to enrich unloaded types
        library.reset()
        await manager_mock.enrich(enrich=EnrichTypesRemote.ARTISTS, force=True)

        enriched_types_track = manager_mock.types_enriched[LoadTypesRemote.SAVED_TRACKS]
        assert enriched_types_track == {EnrichTypesRemote.ARTISTS}
        assert not library.enrich_tracks_args["albums"]
        assert library.enrich_tracks_args["artists"]

        enriched_types_artist = manager_mock.types_enriched[LoadTypesRemote.SAVED_ARTISTS]
        assert not enriched_types_artist
        assert not library.enrich_saved_artists_args["tracks"]
