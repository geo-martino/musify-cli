from pydantic import Field
from pydantic_settings import CliSubCommand

from mytunes_cli._base import BaseCommand
from mytunes_cli.operations.album.utils import AlbumDownload


class Album(BaseCommand):
    download: CliSubCommand[AlbumDownload] = Field(
        description="Open sites to download albums from playlists on a remote service.",
    )
