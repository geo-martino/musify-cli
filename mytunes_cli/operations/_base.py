import inspect
from abc import abstractmethod
from collections.abc import MutableMapping, Sequence, Mapping, Iterable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Self, Literal

from mytunes.annotation import StrippedString
from mytunes.core.api import HasAPI
from mytunes.core.library import Library, RemoteLibrary, RemoteMutableLibrary
from mytunes.exception import MyTunesValidationError
from mytunes.local.library import LocalLibrary
from mytunes.local.track import LocalTrack
from pydantic import Field, model_validator
from pydantic.alias_generators import to_snake

from mytunes_cli import PROGRAM_NAME
from mytunes_cli.state import GlobalState, HasGlobalState


# noinspection PyAbstractClass
class Operation(HasGlobalState):
    @property
    def operation_name(self) -> str | None:
        """The name of operation formatted to be appropriate for logging."""
        return to_snake(type(self).__name__).replace("_", " ").title()

    async def cli_cmd(self) -> None:
        """Run the operation from the CLI invocation. Wraps py:meth:`run` with supporting calls."""
        async with self:
            await self.load()

            # only attempt to log start here if the func requires no additional args
            if inspect.getfullargspec(self._log_start).args == ["self"]:
                self._log_start()

            await self.run()

    async def load(self) -> None:
        """Run any necessary load operations before starting the operation."""
        pass

    @abstractmethod
    async def run(self) -> None:
        """Run the operation."""
        raise NotImplementedError

    def _log_start(self, *args, **kwargs) -> None:
        """Log the start of the operation."""
        pass

    async def __aenter__(self) -> Self:
        self.state.paths.__enter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return self.state.paths.__exit__(exc_type, exc_val, exc_tb)


# noinspection PyAbstractClass
class LibraryOperation(Operation):
    @model_validator(mode="after")
    def _validate_libraries_configured(self) -> Self:
        if self.state.libraries:
            return self

        path = (self.state.paths.config / self.state._default_filename).with_suffix(".yaml")
        raise MyTunesValidationError(
            f"Cannot run {PROGRAM_NAME}: No libraries configured. "
            f"Create a libraries config file at {str(path)!r}"
        )


# noinspection PyAbstractClass
class SingleLibraryOperation(LibraryOperation):
    library_name: str = Field(
        description="The name of the library.",
        validation_alias="library",
    )

    @property
    def library(self) -> Library:
        return self.state.get_library(self.library_name)

    @property
    def source(self) -> str:
        return self.library.source.title()

    @model_validator(mode="after")
    def _validate_library_exists(self) -> Self:
        try:
            assert self.library
        except (AssertionError, KeyError, TypeError) as exc:
            raise MyTunesValidationError(str(exc))

        return self

    async def __aenter__(self) -> Self:
        await super().__aenter__()  # need to enter paths context first
        await self.library.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.library.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)


# noinspection PyAbstractClass
class LocalLibraryOperation(SingleLibraryOperation):
    @model_validator(mode="after")
    def _set_remote_source_on_local(self) -> Self:
        library = self.library
        if isinstance(self, RemoteAPIOperation):
            library.tracks_context.remote_source = self.api.source
        return self

    @property
    def library(self) -> LocalLibrary:
        return self.state.get_local_library(self.library_name)


# noinspection PyAbstractClass
class RemoteLibraryOperation(SingleLibraryOperation):
    @property
    def library(self) -> RemoteMutableLibrary:
        return self.state.get_mutable_remote_library(self.library_name)


# noinspection PyAbstractClass
class RemoteAPIOperation(LibraryOperation, HasAPI):
    @property
    def source(self) -> str:
        return self.api.source.title()

    @model_validator(mode="before")
    @classmethod
    def _set_api_from_library[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        name = cls._get_value_from_data(data, "api")
        if not isinstance(name, str):
            return data

        state = cls._get_value_from_data(data, "state")
        if not isinstance(state, GlobalState):
            return name

        data["api"] = state.get_remote_library(name).api
        return data

    async def __aenter__(self) -> Self:
        await super().__aenter__()  # need to enter paths context first
        await self.api.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)


# noinspection PyAbstractClass
class CrossLibraryOperation[SL: Library, TL: Library](LibraryOperation):
    source_name: StrippedString = Field(
        description="The name of the source library.",
        validation_alias="source",
    )
    target_name: StrippedString = Field(
        description="The name of the target library.",
        validation_alias="target",
    )

    @property
    def source(self) -> SL:
        return self.state.get_library(self.source_name)

    @property
    def target(self) -> TL:
        return self.state.get_library(self.target_name)

    @model_validator(mode="after")
    def _validate_source_library_exists(self) -> Self:
        try:
            assert self.source
        except (AssertionError, KeyError, TypeError) as exc:
            raise MyTunesValidationError(str(exc))

        return self

    @model_validator(mode="after")
    def _validate_target_library_exists(self) -> Self:
        try:
            assert self.target
        except (AssertionError, KeyError, TypeError) as exc:
            raise MyTunesValidationError(str(exc))

        return self

    async def __aenter__(self) -> Self:
        await super().__aenter__()  # need to enter paths context first
        await self.source.__aenter__()
        await self.target.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.source.__aexit__(exc_type, exc_val, exc_tb)
        await self.target.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)


# noinspection PyAbstractClass
class LocalToRemoteOperation(CrossLibraryOperation[LocalLibrary, RemoteMutableLibrary]):
    @property
    def source(self) -> LocalLibrary:
        return self.state.get_local_library(self.source_name)

    @property
    def target(self) -> RemoteMutableLibrary:
        return self.state.get_mutable_remote_library(self.target_name)

    @model_validator(mode="after")
    def _set_remote_source_on_local(self) -> Self:
        self.source.tracks_context.remote_source = self.target.source
        return self


# noinspection PyAbstractClass
class RemoteToLocalOperation(CrossLibraryOperation[RemoteLibrary, LocalLibrary]):
    @property
    def source(self) -> RemoteLibrary:
        return self.state.get_remote_library(self.source_name)

    @property
    def target(self) -> LocalLibrary:
        return self.state.get_local_library(self.target_name)

    @model_validator(mode="after")
    def _set_remote_source_on_local(self) -> Self:
        self.target.tracks_context.remote_source = self.source.source
        return self


TAGS_ALL = sorted({tag for kls in LocalTrack.registered_submodels for tag in kls.__tag_attributes__})
TAGS_SAVE = sorted({tag.split(".")[0] for kls in LocalTrack.registered_submodels for tag in kls.__tag_fields__})


# noinspection PyAbstractClass
class TagOperation(Operation):
    include: Sequence[Literal[*TAGS_SAVE]] = Field(
        description="The tags to include when updating tracks.",
        default_factory=tuple,
    )
    exclude: Sequence[Literal[*TAGS_SAVE]] = Field(
        description="The tags to exclude when updating tracks.",
        default_factory=tuple,
    )
    replace: bool = Field(
        description="Whether to replace existing tags. If False, existing tags will be preserved.",
        default=False,
    )
    save: bool = Field(
        description="Whether to save the metadata back to files for tracks with changed URIs.",
        default=True,
    )

    async def _save_tracks(self, library: LocalLibrary, tracks: Sequence[LocalTrack] = ()) -> None:
        if not self.save:
            return
        if not library.track_total and not tracks:
            return

        with self._switch_library_tracks(library, tracks) as lib:
            message = f"Saving tags for {lib.track_total} tracks:"
            tags = self._logger.format_list_to_string(tag for tag in self.include or TAGS_SAVE if tag not in self.exclude)
            self._logger.info(message, header=1, hidden=tags, new_line_start=True)

            results = await lib.save_tracks(
                include=self.include, exclude=self.exclude, replace=self.replace, dry_run=self.state.dry_run,
            )
            self._log_save_tracks(results, lib)

    @staticmethod
    @contextmanager
    def _switch_library_tracks(library: LocalLibrary, tracks: Sequence[LocalTrack] = ()) -> Generator[LocalLibrary]:
        if not tracks:
            yield library
            return

        # temporarily switch out the library tracks to process only the given tracks
        # do not try to copy the library with new tracks as this will break save state management
        original = list(library.tracks)
        library.tracks.replace(tracks)

        yield library

        library.tracks.replace(original)

    def _log_save_tracks(self, results: Mapping[Path, Iterable[str]], library: LocalLibrary) -> None:
        library.log_save_tracks_results(results, dry_run=self.state.dry_run)

        log_prefix = "Would have set" if self.state.dry_run else "Set"
        results = {path: tags for path, tags in results.items() if tags}
        self._logger.info(f"[green]{log_prefix} tags for {len(results)} tracks[/]")
