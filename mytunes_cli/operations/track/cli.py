from pydantic import Field
from pydantic_settings import CliSubCommand

from mytunes_cli._base import BaseCommand
from mytunes_cli.operations.track.match import LocalTrackSearch, LocalTrackCheck
from mytunes_cli.operations.track.tags import PullTags, RuleTags
from mytunes_cli.operations.track.utils import Download, Save


class Tags(BaseCommand):
    pull: CliSubCommand[PullTags] = Field(
        description="Set tags on local tracks by pulling them from their matches a remote service.",
    )
    rules: CliSubCommand[RuleTags] = Field(
        description="Set tags on local tracks from a set of rules.",
    )


class Track(BaseCommand):
    search: CliSubCommand[LocalTrackSearch] = Field(
        description="Search for URI matches for tracks in a local library.",
    )
    check: CliSubCommand[LocalTrackCheck] = Field(
        description="Check URI matches for tracks in a local library.",
    )
    tags: CliSubCommand[Tags] = Field(
        description="Set tags on local tracks.",
    )

    download: CliSubCommand[Download] = Field(
        description="Open sites to download tracks from playlists on a remote service.",
    )
    save: CliSubCommand[Save] = Field(
        description="Save the currently loaded tracks. Usually used as a last step in a pipeline operation.",
    )
