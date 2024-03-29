from collections.abc import Iterable
from typing import Any

from musify.shared.exception import MusifyError
from musify.shared.utils import SafeDict


class ConfigError(MusifyError):
    """
    Exception raised when processing config gives an exception.

    :param key: The key that caused the error.
    :param value: The value that caused the error.
    :param message: Explanation of the error.
    """
    def __init__(self, message: str = "Could not process config", key: Any | None = None, value: Any | None = None):
        suffix = []

        key = "->".join(key) if isinstance(key, Iterable) and not isinstance(key, str) else key
        if key and "{key}" in message:
            message = message.format_map(SafeDict(key=key))
        elif key:
            suffix.append(f"key='{key}'")

        value = ", ".join(value) if isinstance(value, Iterable) and not isinstance(value, str) else value
        if value and "{value}" in message:
            message = message.format_map(SafeDict(value=value))
        elif value:
            suffix.append(f"value='{value}'")

        self.key = key
        self.value = value
        self.message = message
        super().__init__(": ".join([message, " | ".join(suffix)]))
