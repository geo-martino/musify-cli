from typing import Annotated

from mytunes.core.library import Library, RemoteLibrary
from mytunes.core.playlist import Playlist
from mytunes.core.properties.name import HasName
from mytunes.local.album import LocalAlbumCollection
from mytunes.local.folder import Folder
from mytunes.local.library import LocalLibrary
from mytunes.processors.filters import Filter
from mytunes.processors.filters.composite import IncludeExcludeFilter
from mytunes.processors.filters.values import NameFilter
from pydantic import Field, BeforeValidator, field_validator

from mytunes_cli._base import BaseSettings
from mytunes_cli.state import HasGlobalState

type FilterT = Annotated[
    NameFilter | IncludeExcludeFilter[HasName, NameFilter, NameFilter] | None,
    Field(discriminator=Filter.__discriminator_field__),
    BeforeValidator(NameFilter.from_names),
]


# noinspection PyAbstractClass
class HasFilter[FT: HasName](BaseSettings):
    filter: FilterT = Field(
        description="The items to process. If not set, all available items will be processed.",
        default=None,
        validation_alias="items",
    )

    @field_validator("filter", mode="before", check_fields=True)
    @classmethod
    def _split_string[T](cls, value: T | str) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return value.split(",")

    def _apply_filter(self, items: list[FT]) -> list[FT]:
        if isinstance(self.filter, Filter):
            items = self.filter.apply(items)
        return items


# noinspection PyAbstractClass
class HasPlaylistFilter[FT: Playlist](HasGlobalState, HasFilter[FT]):
    filter: FilterT = Field(
        description="The playlists to process. If not set, all available playlists will be processed.",
        default=None,
        validation_alias="playlists",
    )

    async def _load_playlists(self, library: Library) -> None:
        if isinstance(library, LocalLibrary):
            await library.load_tracks()  # always need to load tracks first for local libraries

        log_state = not self.state.get_load_state(library.load_playlists)
        await library.load_playlists()

        if isinstance(library, RemoteLibrary):
            log_state = not self.state.get_load_state(library.load_playlist_items)
            await library.load_playlist_items()

        if log_state:
            library.log_playlists()

    def _get_playlists(self, library: Library) -> list[FT]:
        playlists = list(library.playlists)
        return self._apply_filter(playlists)


# noinspection PyAbstractClass
class HasFolderFilter(HasFilter[Folder]):
    filter: FilterT = Field(
        description="The folders to process. If not set, all available folders will be processed.",
        default=None,
        validation_alias="folders",
    )

    def _get_folders(self, library: LocalLibrary) -> list[Folder]:
        folders = list(library.folders)
        return self._apply_filter(folders)


# noinspection PyAbstractClass
class HasAlbumFilter(HasFilter[LocalAlbumCollection]):
    filter: FilterT = Field(
        description="The albums to process. If not set, all available albums will be processed.",
        default=None,
        validation_alias="albums",
    )

    def _get_albums(self, library: LocalLibrary) -> list[LocalAlbumCollection]:
        albums = list(library.albums)
        return self._apply_filter(albums)
