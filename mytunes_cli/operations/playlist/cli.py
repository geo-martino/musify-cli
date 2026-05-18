from pydantic import Field
from pydantic_settings import CliSubCommand

from mytunes_cli._base import BaseCommand
from mytunes_cli.operations.playlist.core import SyncLocalPlaylists, SyncLocalAndRemotePlaylists, ExportLocalPlaylists
from mytunes_cli.operations.playlist.create import NewMusicPlaylist
from mytunes_cli.operations.playlist.match import LocalPlaylistSearch, LocalPlaylistCheck
from mytunes_cli.operations.playlist.utils import Save


class CreatePlaylists(BaseCommand):
    new_music: CliSubCommand[NewMusicPlaylist] = Field(
        description="Create a new music playlist on a remote service.",
    )


class SyncPlaylists(BaseCommand):
    local: CliSubCommand[SyncLocalPlaylists] = Field(
        description="Sync playlists between local libraries.",
    )
    local_remote: CliSubCommand[SyncLocalAndRemotePlaylists] = Field(
        description="Sync playlists between a local library and a remote service.",
    )


class Playlist(BaseCommand):
    search: CliSubCommand[LocalPlaylistSearch] = Field(
        description="Search for URI matches for playlists in a local library.",
    )
    check: CliSubCommand[LocalPlaylistCheck] = Field(
        description="Check URI matches for playlists in a local library.",
    )

    sync: CliSubCommand[SyncPlaylists] = Field(
        description="Sync playlists between libraries.",
    )
    create: CliSubCommand[CreatePlaylists] = Field(
        description="Create playlists on a remote service.",
    )
    export: CliSubCommand[ExportLocalPlaylists] = Field(
        description="Export static copies of playlists from a local library.",
    )

    save: CliSubCommand[Save] = Field(
        description="Save the currently loaded playlists. Usually used as a last step in a pipeline operation.",
    )
