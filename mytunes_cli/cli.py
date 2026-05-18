import sys
from collections.abc import Sequence
from contextlib import suppress

from mytunes.core.properties.logger import HasLogger
from pydantic import Field
from pydantic.alias_generators import to_snake
from pydantic_settings import CliSubCommand, CliApp, get_subcommand, CliSettingsSource

from mytunes_cli._base import BaseCommand
from mytunes_cli.operations import Operation
from mytunes_cli.operations.album.cli import Album
from mytunes_cli.operations.backup.cli import Backup, Restore
from mytunes_cli.operations.backup.utils import Clean
from mytunes_cli.operations.playlist.cli import Playlist
from mytunes_cli.operations.report.cli import Report
from mytunes_cli.operations.track.cli import Track
from mytunes_cli.operations.utils import Print, Pause
from mytunes_cli.printer import HasPrinter


class CoreCLI(BaseCommand, HasPrinter, HasLogger):
    playlist: CliSubCommand[Playlist] = Field(
        description="Run operations on the playlists of libraries.",
    )
    track: CliSubCommand[Track] = Field(
        description="Run operations on the tracks of libraries.",
    )
    album: CliSubCommand[Album] = Field(
        description="Run operations on the albums of libraries.",
    )

    backup: CliSubCommand[Backup] = Field(
        description="Backup a library by dumping its properties to a file.",
    )
    restore: CliSubCommand[Restore] = Field(
        description="Restore a library from a backup.",
    )
    backup_clean: CliSubCommand[Clean] = Field(
        description="Clean up the backup folder by removing old or outdated backups.",
    )

    report: CliSubCommand[Report] = Field(
        description="Report on stats about libraries and their items.",
    )
    print: CliSubCommand[Print] = Field(
        description="Print information about items from a remote service.",
    )
    pause: CliSubCommand[Pause] = Field(
        description="Pause an operation and display a message.",
    )

    @property
    def operation(self) -> Operation:
        """The operation to execute."""
        command = self
        while (sub_command := get_subcommand(command, is_required=False)) is not None:
            command = sub_command

        return command if isinstance(command, Operation) else None

    @classmethod
    def split_args(cls, args: Sequence[str]) -> tuple[Sequence[str], Sequence[str]]:
        """
        Split the given CLI arguments to those that correspond to the global args and the operation to run.

        This is largely a workaround as parsing the args to the global state and then parsing
        the same args with the operation causes odd parsing behaviour.
        """
        sub_command_idx = next((idx for idx, arg in enumerate(args) if to_snake(arg) in cls.model_fields), len(args))
        return args[1:sub_command_idx], args[sub_command_idx:]

    @staticmethod
    def has_help_arg(args: Sequence[str] = None) -> bool:
        if args is None:
            args = sys.argv[1:]
        return any(flag in args for flag in ("-h", "--help"))

    @classmethod
    def cli_help(cls, args: Sequence[str] = None) -> None:
        """Run the help command."""
        if args is None:
            args = sys.argv[1:]

        print()
        with suppress(SystemExit):  # handle system exit after
            source = CliSettingsSource(cls, cli_parse_args=list(args))
            if not args or not cls.has_help_arg(args):
                CliApp.print_help(cls, cli_settings_source=source)

    def cli_cmd(self) -> None:
        self.log_operation()
        super().cli_cmd()

    def log_operation(self) -> None:
        """Log the operation and its current settings."""
        operation = self.operation
        if operation is None:
            return

        name = self.operation.operation_name
        if not name:
            return

        self.printer.print_function_header(name.upper())

        dump = self.operation.model_dump_yaml()
        self._logger.debug(f"{name} settings:\n{dump}")
