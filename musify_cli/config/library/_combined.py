"""
Sets up and configures the parser for all arguments relating to :py:class:`Library` objects
and their related objects/configuration.
"""
from collections.abc import Mapping, Iterable
from functools import partial
from typing import Self, Annotated, Any

from pydantic import BaseModel, Field, BeforeValidator, model_validator

from musify_cli.config.library._core import LibraryConfig
from musify_cli.config.library.local import LocalLibraryConfig, LOCAL_LIBRARY_CONFIG
from musify_cli.config.library.remote import RemoteLibraryConfig, REMOTE_LIBRARY_CONFIG
from musify_cli.exception import ParserError

LIBRARY_TYPES = {str(lib.source) for lib in LOCAL_LIBRARY_CONFIG | REMOTE_LIBRARY_CONFIG}


def create_library_config[T: LibraryConfig](kwargs: Any, config_map: Iterable[type[T]]) -> T:
    """Configure library config from the given input."""
    if isinstance(kwargs, LibraryConfig):
        return kwargs
    elif not isinstance(kwargs, Mapping):
        raise ParserError("Unrecognised input type")

    library_key = kwargs.get(type_key := "type", "").strip().casefold()
    library_cls = next((cls for cls in config_map if str(cls.source).casefold() == library_key), None)
    if library_cls is None:
        raise ParserError("Unrecognised library type", key=type_key, value=library_key)

    return library_cls(**kwargs)


type LocalLibraryType = Annotated[
    LocalLibraryConfig, BeforeValidator(partial(create_library_config, config_map=LOCAL_LIBRARY_CONFIG))
]
type RemoteLibraryType = Annotated[
    RemoteLibraryConfig, BeforeValidator(partial(create_library_config, config_map=REMOTE_LIBRARY_CONFIG))
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
        default_factory=LibraryTarget,
    )
    local: LocalLibraryType | list[LocalLibraryType] = Field(
        description="Configuration for all available local libraries",
    )
    remote: RemoteLibraryType | list[RemoteLibraryType] = Field(
        description="Configuration for all available remote libraries",
    )

    @model_validator(mode="after")
    def extract_local_library_from_target(self) -> Self:
        """When many local libraries are configured, set the local library from the target name"""
        if not isinstance(self.local, list):
            return self

        if not self.target.local:
            raise ParserError("Many local libraries given but no target specified", key="local")

        try:
            self.local = next(iter(lib for lib in self.local if lib.name == self.target.local))
        except StopIteration:
            raise ParserError(
                "The given local target does not correspond to any configured local library", key="local"
                )

        return self

    @model_validator(mode="after")
    def extract_remote_library_from_target(self) -> Self:
        """When many remote libraries are configured, set the remote library from the target name"""
        if not isinstance(self.remote, list):
            return self

        if not self.target.remote:
            raise ParserError("Many remote libraries given but no target specified", key="local")

        try:
            self.remote = next(iter(lib for lib in self.remote if lib.name == self.target.remote))
        except StopIteration:
            raise ParserError(
                "The given remote target does not correspond to any configured remote library", key="remote"
            )

        return self
