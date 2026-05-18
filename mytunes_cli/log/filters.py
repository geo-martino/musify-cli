"""
All logging filters specific to this package.
"""
import inspect
import logging.handlers
import re
from pathlib import Path

from mytunes import PROGRAM_NAME

from mytunes_cli import PACKAGE_ROOT


def format_full_func_name(record: logging.LogRecord, width: int = 40) -> None:
    """
    Set fully qualified path name to function including class name to the given record.
    Optionally, provide a max ``width`` to attempt to truncate the path name to
    by taking only the first letter of each part of the path until the length is equal to ``width``.
    """
    calls = inspect.stack()
    log_function_name = "_log"
    function_names = [call.function.casefold() for call in calls]

    last_call = None
    if log_function_name in function_names:
        last_call = calls[len(calls) - function_names[::-1].index(log_function_name) + 1]

    if last_call is not None:
        record.pathname = last_call.filename
        record.lineno = last_call.lineno
        record.funcName = last_call.function
        record.filename = Path(record.pathname).name
        record.module = record.name.split(".")[-1]

    if last_call is None or "self" not in last_call.frame.f_locals:
        path_split = record.name.split(".")
        if record.funcName != "<module>":
            path_split.append(record.funcName)
    else:
        # is a valid and initialised object, extract the class name and determine path to call function from stack
        cls = type(last_call.frame.f_locals["self"])
        path = Path(inspect.getfile(cls)).with_suffix("")
        if path.is_relative_to(PACKAGE_ROOT):
            path = path.relative_to(PACKAGE_ROOT)

        parts = iter(path.parts)
        package_name = next((part for part in parts if part.startswith(PROGRAM_NAME.casefold())), None)
        if not package_name:
            path_split = list(path.parts)
        else:
            path_split = [package_name] + list(parts) + [cls.__name__, last_call.function.split(".")[-1]]

    # truncate long paths by taking first letters of each part until short enough
    path = ".".join(path_split)
    for i, part in enumerate(path_split):
        if len(path) <= width:
            break
        if not part:
            continue

        # take all upper case characters if they exist in part, else, if all lower case, take first letter
        path_split[i] = re.sub("[a-z_]+", "", part) if re.match("[A-Z]", part) else part[0]
        path = ".".join(path_split)

    record.funcName = path


class AddName(logging.Filter):
    """
    Filter for adding the fully qualified module name to the log record.

    :param module_width: The maximum width a module string can be in the log record.
        Truncates module string if longer that this length.
    """

    def __init__(self, name: str = "", module_width: int = 40):
        super().__init__(name)
        self.module_width = module_width

    def filter(self, record: logging.LogRecord) -> logging.LogRecord | None:
        format_full_func_name(record, width=self.module_width)
        return record
