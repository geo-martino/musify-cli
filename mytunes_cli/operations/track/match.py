from collections.abc import Sequence
from typing import Literal

from mytunes.local.album import LocalAlbumCollection
from mytunes.local.track import LocalTrack
from pydantic import Field
from pydantic_settings import CliSuppress

from mytunes_cli.operations._base import TagOperation, LocalLibraryOperation
from mytunes_cli.operations._filters import HasAlbumFilter
from mytunes_cli.operations._match import CollectionSearch, CollectionCheck, Match


# noinspection PyAbstractClass
class LocalTrackMatch(Match[LocalAlbumCollection, LocalTrack], LocalLibraryOperation, TagOperation, HasAlbumFilter):
    include: CliSuppress[Sequence[Literal["uri"]]] = Field(
        description="The tags to include when updating tracks.",
        default=("uri",),
    )
    exclude: CliSuppress[Sequence[Literal[None]]] = Field(
        description="The tags to exclude when updating tracks.",
        default_factory=tuple,
    )

    @property
    def items(self) -> list[LocalAlbumCollection]:
        return self._get_albums(self.library)

    async def load(self) -> None:
        log_state = not self.state.get_load_state(self.library.load_tracks)
        await self.library.load_tracks()

        if log_state:
            self.library.log_tracks()

    async def _save(self, items: list[LocalTrack]) -> None:
        return await self._save_tracks(self.library, tracks=items)


class LocalTrackSearch(LocalTrackMatch, CollectionSearch[LocalAlbumCollection, LocalTrack]):
    pass


class LocalTrackCheck(LocalTrackMatch, CollectionCheck[LocalAlbumCollection, LocalTrack]):
    pass
