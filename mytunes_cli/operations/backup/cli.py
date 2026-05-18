from pydantic import Field
from pydantic_settings import CliSubCommand

from mytunes_cli._base import BaseCommand
from mytunes_cli.operations.backup.backup import Backup as BackupOperation
from mytunes_cli.operations.backup.restore import RestoreLocalLibrary, RestoreRemoteLibrary


class Backup(BaseCommand):
    local: CliSubCommand[BackupOperation] = Field(
        description="Backup a local library by dumping its properties to a file.",
    )
    remote: CliSubCommand[BackupOperation] = Field(
        description="Backup a remote library by dumping its properties to a file.",
    )


class Restore(BaseCommand):
    local: CliSubCommand[RestoreLocalLibrary] = Field(
        description="Restore a local library from a backup.",
    )
    remote: CliSubCommand[RestoreRemoteLibrary] = Field(
        description="Restore a remote library from a backup.",
    )
