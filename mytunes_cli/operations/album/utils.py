from mytunes.core.album import HasAlbum
from mytunes.core.playlist import RemotePlaylist
from mytunes.processors.download import StoreManager

from mytunes_cli.operations._base import RemoteLibraryOperation
from mytunes_cli.operations._filters import HasPlaylistFilter


class AlbumDownload(RemoteLibraryOperation, StoreManager, HasPlaylistFilter[RemotePlaylist]):
    async def load(self) -> None:
        await self._load_playlists(self.library)

    async def run(self) -> None:
        playlists = self._get_playlists(self.library)
        albums = []
        for playlist in playlists:
            for item in playlist.items:
                if isinstance(item, HasAlbum) and item.album not in albums:
                    albums.append(item.album)

        self.open_sites_for_items(albums)
