from abc import abstractmethod
from datetime import date

from mytunes.annotation import StrippedString
from mytunes.core.album import RemoteAlbumCollection, AlbumCollection
from mytunes.core.api import HasLibraryEndpoints
from mytunes.core.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteEndpoints, PlaylistLibraryEndpoints
from mytunes.core.collection import SyncRemoteResult
from mytunes.core.playlist import RemoteMutablePlaylist
from mytunes.core.track import RemoteTrack
from mytunes.exception import APIError
from pydantic import Field

from mytunes_cli.operations._base import RemoteLibraryOperation


# noinspection PyAbstractClass
class CreateRemotePlaylistOperation(RemoteLibraryOperation):
    name: StrippedString = Field(
        description="The name to give to the playlist.",
    )

    @property
    @abstractmethod
    def tracks(self) -> list[RemoteTrack]:
        """The tracks to add to the playlist."""
        raise NotImplementedError

    async def run(self) -> None:
        self._logger.info(self._log_message, header=1)

        result = await self._create_playlist()
        self.library.log_sync_results([result])

        log_prefix = "Would have added" if self.state.dry_run else "Added"
        message = f"{log_prefix} {result.added} new tracks to playlist: '{result.name}'"
        self._logger.info(f"[green]{message}[/]")

    @property
    def _log_message(self) -> str:
        """The message to log to the user."""
        return f"Creating {self.name!r} {self.source} playlist of {len(self.tracks)} tracks"

    async def _create_playlist(self) -> SyncRemoteResult:
        api: HasPlaylistEndpoints[
            PlaylistReadWriteEndpoints | HasLibraryEndpoints[PlaylistLibraryEndpoints]
        ] = self.library.api

        playlist: RemoteMutablePlaylist = await api.playlists.library.get_or_create(self.name)
        if not isinstance(playlist, RemoteMutablePlaylist):
            raise APIError(f"Playlist {self.name!r} is not writeable.")

        playlist.tracks.clear()
        playlist.tracks.extend(self.tracks)

        return await playlist.sync_items(
            api, kind="sync", sync_filter=self.library.sync_filter, dry_run=self.state.dry_run
        )


class NewMusicPlaylist(CreateRemotePlaylistOperation):
    name: StrippedString = Field(
        description="The name to give to the playlist.",
        default="New Music",
    )
    from_date: date | None = Field(
        description="The earliest release date of music released by an artist to add to the playlist.",
        default=date.min,
    )
    to_date: date | None = Field(
        description="The latest release date of music released by an artist to add to the playlist.",
        default=date.max,
    )

    async def load(self) -> None:
        log_state = not self.state.get_load_state(self.library.load_library_artist_albums)

        await self.library.load_library_artists()
        await self.library.load_library_artist_albums()

        if log_state:
            self.library.log_artists()

    @property
    def albums(self) -> list[RemoteAlbumCollection]:
        def match_date(alb: RemoteAlbumCollection) -> bool:
            """Match start and end dates to the release date of the given ``alb``"""
            if not isinstance(alb, AlbumCollection) or not alb.total:  # no items to add to playlist
                return False

            dt = date(year=alb.released_at.year, month=alb.released_at.month or 1, day=alb.released_at.day or 1)
            result = self.from_date <= dt <= self.to_date

            return result

        albums = filter(match_date, (album for artist in self.library.artists for album in artist.albums))
        return sorted(albums, key=lambda album: album.released_at, reverse=True)

    @property
    def tracks(self) -> list[RemoteTrack]:
        return [track for album in self.albums for track in album.tracks]

    @property
    def _log_message(self) -> str:
        return (
            f"Creating {self.name!r} {self.source} playlist "
            f"for {len(self.tracks)} new tracks from {len(self.albums)} albums "
            f"by followed artists released between {self.from_date} and {self.to_date}\33[0m"
        )
