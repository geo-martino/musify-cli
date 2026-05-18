from collections.abc import Sequence, Generator
from contextlib import contextmanager
from typing import Literal

from mytunes.core.library import RemoteLibrary
from mytunes.core.playlist import RemotePlaylist
from mytunes.local._collection import LocalLibrary
from mytunes.local.playlist import LocalPlaylist
from mytunes.processors.search import SearchResult
from pydantic import Field
from pydantic_settings import CliSuppress

from mytunes_cli.operations._base import LocalLibraryOperation
from mytunes_cli.operations._filters import HasPlaylistFilter
from mytunes_cli.operations._match import Match, ItemSearch, ItemCheck


# noinspection PyAbstractClass
class LocalPlaylistMatch(Match[LocalPlaylist, LocalPlaylist], LocalLibraryOperation, HasPlaylistFilter[LocalPlaylist]):
    save: CliSuppress[Literal[False]] = Field(
        description="DISABLE: Not supported by base package.",
        # description="Whether to save the playlist data back to files for playlists with changed URIs.",
        default=False,
    )

    @property
    def items(self) -> list[LocalPlaylist]:
        return self._get_playlists(self.library)

    @property
    def result_key(self) -> str:
        return f"{self.library.type} library - {self.library_name}"

    async def load(self) -> None:
        await self.library.load()

    async def _save(self, playlists: Sequence[LocalPlaylist]) -> None:
        if not self.save or not playlists:
            return

        with self._switch_library_playlists(self.library, playlists=playlists) as lib:
            results = await lib.save_playlists(dry_run=self.state.dry_run)
            lib.log_save_playlists_results(results)

    @staticmethod
    @contextmanager
    def _switch_library_playlists(
            library: LocalLibrary, playlists: Sequence[LocalPlaylist] = ()
    ) -> Generator[LocalLibrary]:
        if not playlists:
            yield library
            return

        # temporarily switch out the library playlists to process only the given playlists
        # do not try to copy the library with new playlists as this will break save state management
        original = list(library.playlists)
        library.playlists.replace(playlists)

        yield library

        library.playlists.replace(original)


class LocalPlaylistSearch(LocalPlaylistMatch, ItemSearch[LocalPlaylist]):
    @property
    def remote(self) -> RemoteLibrary:
        return next(
            lib for lib in self.state.libraries.values() if isinstance(lib, RemoteLibrary) and lib.api is self.api
        )

    async def load(self) -> None:
        await super().load()
        await self.remote.load_playlists()

    async def _match(self) -> tuple[LocalPlaylist, ...]:
        """Override querying API and just try to match by name within the current remote library."""
        result = self._match_by_name()
        result = result.merge(await self.search_many(result.unmatched, name=self.result_key))

        self.log_results(result)

        return tuple(result.matched)

    def _match_by_name(self) -> SearchResult[LocalPlaylist, RemotePlaylist]:
        matched: list[LocalPlaylist] = []
        matches: list[RemotePlaylist] = []
        unmatched: list[LocalPlaylist] = []
        skipped: list[LocalPlaylist] = []

        for playlist in self.items:
            if playlist.has_uri is not None:
                skipped.append(playlist)
                continue

            match = next((pl for pl in self.remote.playlists if pl.name == playlist.name), None)
            if not match:
                unmatched.append(playlist)
                continue

            playlist.uri = match.uri
            matched.append(playlist)
            matches.append(match)

        return SearchResult[LocalPlaylist, RemotePlaylist](
            name=self.result_key,
            matched=matched,
            matches=matches,
            unmatched=unmatched,
            skipped=skipped,
        )


class LocalPlaylistCheck(LocalPlaylistMatch, ItemCheck[LocalPlaylist]):
    pass
