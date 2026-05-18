from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

from mytunes.core.properties.path import SystemPath
from pydantic import ValidationError


def get_path[T](data: T) -> T | Path:
    """Attempt to extract a path from the given data, if found."""
    match data:
        case str() | Path() as path:
            return Path(path)
        case Mapping() as mapping:
            with suppress(ValidationError):
                path = SystemPath.model_validate(mapping).path
            return path if path is not None else mapping  # might be actual config
        case _:
            return data
