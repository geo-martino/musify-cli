import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Any, Self

from mytunes import PROGRAM_NAME
from mytunes.core.properties.path import SystemPath
from pydantic import BeforeValidator, Field, model_validator, AfterValidator
from pydantic_core import PydanticCustomError

from mytunes_cli._base import BaseSettings


def is_directory_path(path: Path) -> Path:
    """Check if a path is a directory without checking existence."""
    if path.is_dir() or not path.suffix:
        return path
    else:
        raise PydanticCustomError('path_not_directory', 'Path does not point to a directory')


type DirectoryPath = Annotated[
    Path,
    BeforeValidator(SystemPath.get_current_system_path),
    AfterValidator(is_directory_path)
]


class GlobalPaths(BaseSettings):
    application: DirectoryPath = Field(
        description="The directory to as the base directory for all application directories.",
        default=SystemPath(
            windows=PureWindowsPath(rf"C:\Program Files\{PROGRAM_NAME}"),
            mac=PurePosixPath(f"/Library/Containers/{PROGRAM_NAME}"),
            linux=PurePosixPath(f"/var/lib/{PROGRAM_NAME}"),
        ),
        validation_alias="app",
    )

    config: DirectoryPath = Field(
        description=(
            "The directory to use for config files. "
            "May either be a full path or relative path to the application directory."
        ),
        default=Path("config"),
    )
    logs: DirectoryPath = Field(
        description=(
            "The directory to use for log files. "
            "May either be a full path or relative path to the application directory."
        ),
        default=Path("logs"),
    )
    cache: DirectoryPath = Field(
        description=(
            "The directory to use for caches. "
            "May either be a full path or relative path to the application directory."
        ),
        default=Path("cache"),
    )
    token: DirectoryPath = Field(
        description=(
            "The directory to use for token files. "
            "May either be a full path or relative path to the application directory."
        ),
        default=Path("token")
    )

    @model_validator(mode="before")
    @classmethod
    def _from_application_path[T](cls, data: T | str | Path) -> T | dict[str, Any]:
        if not isinstance(data, (str, Path)):
            return data
        return dict(application=data)

    def __enter__(self) -> Self:
        for name, value in vars(self).items():
            if name not in type(self).model_fields or not isinstance(value, Path):
                continue
            self._setup_path(name, value)

        return self

    def _setup_path(self, field_name: str, path: Path) -> None:
        if not path.is_absolute():
            path = self.application / path
            self.__dict__[field_name] = path

        path.mkdir(parents=True, exist_ok=True)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        for name, value in reversed(vars(self).items()):  # process application path last
            if name not in type(self).model_fields or not isinstance(value, Path):
                continue
            self._teardown_path(value)

    @classmethod
    def _teardown_path(cls, path: Path) -> None:
        for root, dirs, files in os.walk(path, topdown=False):
            root = Path(root)
            files = set(map(root.joinpath, files))
            hidden_files = set(filter(cls._is_hidden, files))

            if not dirs and not files - hidden_files:
                for file in hidden_files:  # clear hidden files
                    os.remove(root.joinpath(file))
                os.rmdir(root)

    @staticmethod
    def _is_hidden(path: Path) -> bool:
        if sys.platform in ("linux", "darwin"):
            return path.name.startswith('.')
        return False  # TODO: not sure how to check this on windows
