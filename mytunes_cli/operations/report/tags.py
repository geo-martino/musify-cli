from collections.abc import Sequence, Collection
from typing import Annotated, Literal

from mytunes.annotation import TO_TUPLE
from mytunes.core.properties.name import HasName
from mytunes.local.album import LocalAlbumCollection
from mytunes.local.track import LocalTrack
from mytunes.logger import Logger
from mytunes.result import Result, MapLogFormatter
from pydantic import Field, OnErrorOmit
from rich.table import Table

from mytunes_cli.operations._base import LocalLibraryOperation, TAGS_ALL
from mytunes_cli.operations._filters import HasAlbumFilter
from mytunes_cli.operations.report._base import ReportOperation


class MissingTagResult[IT: HasName](Result):
    item: IT = Field(
        description="The item with missing tags.",
    )
    tags: Annotated[
        Sequence[str],
        TO_TUPLE,
        MapLogFormatter(
            value=lambda x: Logger.format_list_to_string(x),
            colour="red",
            condition=lambda x: len(x) > 0,
            include_name_in_log=False
        ),
    ] = Field(
        description="The tags that were missing from the item.",
        default_factory=tuple,
    )

    @staticmethod
    def generate_tables(results: dict[str, list[MissingTagResult]]) -> list[Table]:
        tables: list[Table] = []
        for album_name, album_results in results.items():
            album_results = {result.item.name: result for result in album_results}

            header = Logger.generate_message(f"[red]{album_name}[/]", header=1)
            table = MissingTagResult.generate_table(album_results, title=header)
            tables.append(table)

        return tables


class MissingTagReport(ReportOperation[list[MissingTagResult[LocalTrack]]], LocalLibraryOperation, HasAlbumFilter):
    tags: Sequence[OnErrorOmit[Literal[*TAGS_ALL]]] = Field(
        description="The tags to check.",
        default=TAGS_ALL,
    )
    match_all: bool = Field(
        description=(
            "When True, item counts as missing tags if item is missing ``all`` of the given tags. "
            "When False, item counts as missing tags when missing only one of the given tags."
        ),
        default=False,
    )

    @property
    def _tag_map(self) -> dict[str, str]:
        # map tag names with expected attribute names to check on
        mapped_tags: dict[str, str] = {
            "uri": "has_uri",
        }

        return {tag: mapped_tags.get(tag, tag) for tag in self.tags}

    async def load(self) -> None:
        log_state = not self.state.get_load_state(self.library.load_tracks)
        await self.library.load_tracks()

        if log_state:
            self.library.log_tracks()

    async def run(self) -> None:
        albums = self._get_albums(self.library)
        self._log_start(albums)

        results = self._get_results(albums)
        if results:
            self._log_results(results)

    def _get_results(self, albums: list[LocalAlbumCollection]) -> dict[str, list[MissingTagResult[LocalTrack]]]:
        results: dict[str, list[MissingTagResult[LocalTrack]]] = {}

        for album in albums:
            result = list(filter(None, map(self._get_result, album.items)))
            self._add_result_by_name(album.name, result, results)

        return results

    def _get_result(self, item: LocalTrack) -> MissingTagResult | None:
        missing: list[str] = []
        for name, tag in self._tag_map.items():
            value = getattr(item, tag)
            match value:
                case None:
                    missing.append(name)
                case Collection() if not value:
                    missing.append(name)

        if not missing:
            return None
        elif self.match_all and not all(name in missing for name in self._tag_map):
            return None

        return MissingTagResult(item=item, tags=missing)

    ###########################################################################
    ## Logging
    ###########################################################################
    def _log_start(self, albums: list[LocalAlbumCollection]) -> None:
        total = sum(album.track_total for album in albums)

        message = f"Checking {total} items for {'all' if self.match_all else 'any'} missing tags:"
        hidden = self._logger.format_list_to_string(self.tags)
        self._logger.info(message, header=1, hidden=hidden, new_line_start=True)

    def _log_results(self, results: dict[str, list[MissingTagResult]]) -> None:
        message = "[blue]Found the following missing tags by collection:[/]"
        self._logger.report(message, new_line_start=True, new_line_end=True)

        for table in MissingTagResult.generate_tables(results):
            self._logger.report(table, new_line_end=True)

        missing_type = 'all' if self.match_all else 'any'

        all_missing_tags = []
        for items in results.values():
            for result in items:
                for tag in result.tags:
                    if tag not in all_missing_tags:
                        all_missing_tags.append(tag)

        message = f"Found {sum(map(len, results.values()))} items with {missing_type} missing tags"
        message = f"\t[blue]{message}[/]:"
        hidden = Logger.format_list_to_string(all_missing_tags, final_join_word="&" if self.match_all else "or")

        self._logger.info(message, hidden=hidden)
