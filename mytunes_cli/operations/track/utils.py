from mytunes.core.playlist import RemotePlaylist
from mytunes.processors.download import StoreManager

from mytunes_cli.operations._base import RemoteLibraryOperation, LocalLibraryOperation, TagOperation
from mytunes_cli.operations._filters import HasPlaylistFilter


class Save(LocalLibraryOperation, TagOperation):
    async def run(self) -> None:
        await self._save_tracks(self.library)


class Download(RemoteLibraryOperation, StoreManager, HasPlaylistFilter[RemotePlaylist]):
    async def load(self) -> None:
        await self._load_playlists(self.library)

    async def run(self) -> None:
        playlists = self._get_playlists(self.library)
        self.open_sites_for_collections(playlists)