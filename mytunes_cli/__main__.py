import asyncio
import logging
import sys
import warnings
from collections.abc import Sequence

from pydantic import Field
from pydantic_settings import CliApp, CliSubCommand

from mytunes_cli.cli import CoreCLI
from mytunes_cli.operations.pipeline import Pipeline
from mytunes_cli.printer import Printer
from mytunes_cli.state import GlobalState


class TerminalCLI(CoreCLI):
    pipeline: CliSubCommand[Pipeline] = Field(
        description="Enter pipeline mode",
    )

    @classmethod
    def cli_help(cls, args: Sequence[str] = None) -> None:
        """Run the help command."""
        # merge with global state settings to show global settings alongside subcommands
        kls: type[cls] = type("CLIWithGlobalState", (cls, GlobalState), {})
        # this bit is hacky, just means we can call the super method of the dynamically generated class
        # so avoiding needing to redefine the same logic here
        super(cls, kls.__new__(kls)).cli_help(args)


def main():
    """Run the application CLI."""
    Printer.print_header()
    global_args, operation_args = TerminalCLI.split_args(sys.argv)

    if TerminalCLI.has_help_arg() or not operation_args:
        TerminalCLI.cli_help(operation_args)
        sys.exit(0)

    state = GlobalState.parse_state(global_args)
    with state.paths:
        logging_config = state.parse_logging_config()

        # do this within context to ensure log file is created before paths management clears folders
        printer = Printer(state=state)
        printer.print_sub_header()

    printer.log_global_args(global_args)
    printer.log_operation_args(operation_args)
    printer.log_logging(logging_config)
    printer.log_state()

    try:
        # WORKAROUND: dumping local tracks currently throws too many warnings, just catch them for now
        with warnings.catch_warnings(action="ignore"):
            CliApp.run(
                TerminalCLI, cli_args=list(operation_args), printer=printer, state=state, cli_exit_on_error=True
            )
    except* (Exception, KeyboardInterrupt, asyncio.CancelledError) as exc:
        printer.print_traceback(exc)
        sys.exit(1)
    finally:
        if operation_args:
            printer.print_header()
            printer.print_folders()
            printer.print_time()
            printer.print()

        logging.shutdown()


if __name__ == "__main__":
    main()
