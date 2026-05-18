from pydantic import Field
from pydantic_settings import CliSubCommand

from mytunes_cli._base import BaseCommand
from mytunes_cli.operations.report.playlist import PlaylistDifferenceReport
from mytunes_cli.operations.report.tags import MissingTagReport


class Report(BaseCommand):
    playlists: CliSubCommand[PlaylistDifferenceReport] = Field(
        description="Report on the differences of between playlists of libraries.",
    )
    missing_tags: CliSubCommand[MissingTagReport] = Field(
        description="Report on the missing tags of tracks in a local library.",
    )
