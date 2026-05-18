from collections.abc import MutableMapping, Sequence, MutableSequence
from contextlib import suppress
from pathlib import Path
from typing import Any

import yaml
from mytunes.exception import MyTunesError
from mytunes.processors import OptionsProcessor
from mytunes.processors._flow import QuitImmediately
from pydantic import Field, ValidationError, FilePath, model_validator, TypeAdapter
from pydantic_settings import CliSuppress, CliApp, CliPositionalArg

from mytunes_cli.cli import CoreCLI
from mytunes_cli.operations import Operation
from mytunes_cli.printer import HasPrinter, Printer
from .._io.yaml import MultiFileLoader

try:
    import readline  # support command history
except ImportError:
    pass


class Pipeline(Operation, OptionsProcessor, HasPrinter):
    printer: CliSuppress[Printer] = Field(
        description="Printer for headers, footers, and other supporting information",
    )

    operations: CliPositionalArg[MutableSequence[CoreCLI] | None] = Field(
        description=(
            "Path to a YAML file containing configuration for all operations to be executed. "
            "If given, will execute all operations defined and exit. "
            "If not given, an interactive prompt will be used to enter operations and their configuration."
        ),
        default_factory=list,
    )

    @model_validator(mode="before")
    @classmethod
    def _load_operations[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        path = cls._get_value_from_data(data, "operations")
        if isinstance(path, Sequence) and len(path) == 1 and isinstance(path[0], str | Path):
            path = path[0]
        if not isinstance(path, str | Path):
            return data

        state = cls._get_value_from_data(data, "state")
        printer = cls._get_value_from_data(data, "printer")
        path = TypeAdapter(FilePath).validate_python(path)

        with path.open(encoding="utf-8") as file:
            operations_data = yaml.load(file, Loader=MultiFileLoader)

        init_kwargs = dict(state=state, printer=printer)
        data["operations"] = [CoreCLI(**init_kwargs | operation) for operation in operations_data]
        return data

    @property
    def operation_name(self) -> str | None:
        return None  # don't log operation name

    @property
    def _header(self) -> str:
        header = "Pipeline mode"
        sub_header = "Run a series of operations on libraries maintaining state between operations"
        messages = [f"[bold blue]{header}[/]", f"[white]{sub_header}[/]"]
        return "\n\n".join(messages)

    @property
    def _options(self) -> dict[str, str]:
        return {
            "-h --help": "Show usage",
            "q": "Quit pipeline mode",
        }

    async def run(self) -> None:
        if self.operations:
            return self.from_config()

        with suppress(QuitImmediately):
            self.from_input()
        return None

    def from_config(self) -> None:
        message = f"Running pipeline mode on {len(self.operations)} operations:"
        operation_names = "\n- " + "\n- ".join(filter(None, (cli.operation.operation_name for cli in self.operations)))
        self._logger.info(message, header=1, hidden=operation_names, new_line_start=True)

        for operation in self.operations:
            operation.cli_cmd()

    def from_input(self) -> None:
        self._print_help_text()

        message = "Enter command"

        while True:
            args = self._get_user_input(message).casefold().split()
            self.printer.log_operation_args(args)

            if CoreCLI.has_help_arg(args):
                CoreCLI.cli_help(args)
                self._logger.print()
                continue

            try:
                operation = CliApp.run(
                    CoreCLI, cli_args=list(args), printer=self.printer, state=self.state, cli_exit_on_error=True
                )
                self._logger.print()
                self.operations.append(operation)
            except QuitImmediately:  # ensure this raises and isn't caught by other except
                raise
            except SystemExit:  # CliApp triggers an exit on invalid commands
                self.printer.print()
            except MyTunesError as exc:
                self._logger.warning(f"[red]{exc}[/]")
            except ValidationError as exc:
                errors = {error["msg"] for error in exc.errors(include_url=False, include_input=False)}
                for error in errors:
                    self._logger.warning(f"[red]{error}[/]")

                CoreCLI.cli_help(args + ["-h", "--help"])
                self._logger.print()
