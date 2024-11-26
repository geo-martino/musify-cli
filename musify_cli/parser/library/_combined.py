"""
Sets up and configures the parser for all arguments relating to :py:class:`Library` objects
and their related objects/configuration.
"""
from typing import Self, Annotated

from pydantic import BaseModel, Field, BeforeValidator, model_validator

from musify_cli.exception import ParserError
from musify_cli.parser.library.local import LocalLibraryConfig, LOCAL_LIBRARY_TYPES
from musify_cli.parser.library.remote import RemoteLibraryConfig, REMOTE_LIBRARY_TYPES

LIBRARY_TYPES = LOCAL_LIBRARY_TYPES | REMOTE_LIBRARY_TYPES


# noinspection PyTypeChecker
type LocalLibraryAnnotation[T] = Annotated[
    LocalLibraryConfig[T], BeforeValidator(LocalLibraryConfig.create_and_determine_library_type)
]
# noinspection PyTypeChecker
type RemoteLibraryAnnotation[T] = Annotated[
    RemoteLibraryConfig[T], BeforeValidator(RemoteLibraryConfig.create_and_determine_library_type)
]


class LibraryTarget(BaseModel):
    local: str | None = Field(
        description="The name of the local library to use",
        default=None,
    )
    remote: str | None = Field(
        description="The name of the remote library to use",
        default=None,
    )


class LibrariesConfig(BaseModel):
    target: LibraryTarget = Field(
        description="The library targets to use for this run",
        default=LibraryTarget(),
    )
    local: LocalLibraryAnnotation | list[LocalLibraryAnnotation] = Field(
        description="Configuration for all available local libraries",
    )
    remote: RemoteLibraryAnnotation | list[RemoteLibraryAnnotation] = Field(
        description="Configuration for all available remote libraries",
    )

    @model_validator(mode="after")
    def extract_local_library_from_target(self) -> Self:
        if not isinstance(self.local, list):
            return self

        if not self.target.local:
            raise ParserError("Many local libraries given but no target specified", key="local")

        self.local: list[LocalLibraryConfig]
        try:
            self.local = next(iter(lib for lib in self.local if lib.name == self.target.local))
        except StopIteration:
            raise ParserError(
                "The given local target does not correspond to any configured local library", key="local"
                )

        return self

    @model_validator(mode="after")
    def extract_remote_library_from_target(self) -> Self:
        if not isinstance(self.remote, list):
            return self

        if not self.target.remote:
            raise ParserError("Many remote libraries given but no target specified", key="local")

        self.remote: list[RemoteLibraryConfig]
        try:
            self.remote = next(iter(lib for lib in self.remote if lib.name == self.target.remote))
        except StopIteration:
            raise ParserError(
                "The given remote target does not correspond to any configured remote library", key="remote"
            )

        return self
