from typing import Annotated, Sequence

from mytunes._types import DEFAULT_IF_NONE
from mytunes.annotation import ResourceModel, TO_TUPLE
from mytunes.core.library import Library
from mytunes.core.playlist import Playlist
from mytunes.result import LenLogFormatter, CountResult
from pydantic import Field

from mytunes_cli.operations._base import CrossLibraryOperation
from mytunes_cli.operations._filters import HasPlaylistFilter
from mytunes_cli.operations.report._base import ReportOperation


class PlaylistDifferenceResult[IT: ResourceModel](CountResult):
    in_source: Annotated[
        Sequence[IT],
        TO_TUPLE,
        DEFAULT_IF_NONE,
        LenLogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"]),
    ] = Field(
        description="The items in the source playlist.",
        default_factory=tuple,
    )
    in_target: Annotated[
        Sequence[IT],
        TO_TUPLE,
        DEFAULT_IF_NONE,
        LenLogFormatter(width=6, alignment="right", colour="cyan", colour_attributes=["bold"]),
    ] = Field(
        description="The items in the target playlist.",
        default_factory=tuple,
    )
    missing: Annotated[
        Sequence[IT],
        TO_TUPLE,
        DEFAULT_IF_NONE,
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that were present in the source playlist but not the target playlist.",
        default_factory=tuple,
    )
    extra: Annotated[
        Sequence[IT],
        TO_TUPLE,
        DEFAULT_IF_NONE,
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that were present in the target playlist but not the source playlist.",
        default_factory=tuple,
    )


class PlaylistDifferenceReport(
    CrossLibraryOperation[Library, Library], ReportOperation[PlaylistDifferenceResult], HasPlaylistFilter[Playlist]
):
    async def load(self) -> None:
        await self._load_playlists(self.source)
        await self._load_playlists(self.target)

    def _get_results(self) -> dict[str, PlaylistDifferenceResult]:
        results: dict[str, PlaylistDifferenceResult] = {}
        playlists = self._get_playlists(self.source)

        for source in playlists:
            target: Playlist | None = self.target.playlists.get(source)

            result = PlaylistDifferenceResult(
                in_source=source.tracks,
                in_target=target.tracks if target is not None else None,
                missing=source.tracks.difference(target.tracks) if target is not None else None,
                extra=target.tracks.difference(source.tracks) if target is not None else None,
            )
            self._add_result_by_name(source.name, result, results)

        return results

    ###########################################################################
    ## Logging
    ###########################################################################
    def _log_start(self) -> None:
        log_message = (
              "Reporting on playlist differences between "
              f"{self.source_name.replace("_", " ").title()} and "
              f"{self.target_name.replace("_", " ").title()} libraries"
        )
        self._logger.info(log_message, header=1, new_line_start=True)

    def _log_results(self, results: dict[str, PlaylistDifferenceResult]) -> None:
        header = (
            "PLAYLIST DIFFERENCES BETWEEN "
            f"{self.source_name.replace("_", " ").upper()} LIBRARY AND "
            f"{self.target_name.replace("_", " ").upper()} LIBRARY"
        )
        table = PlaylistDifferenceResult.generate_table(results, title=header)

        self._logger.report(table, new_line_start=True)
