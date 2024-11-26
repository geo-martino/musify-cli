import sys
from abc import ABCMeta, abstractmethod
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import Self, Annotated, Type, Any, MutableMapping

from musify.libraries.local.library import LocalLibrary, MusicBee, LIBRARY_CLASSES
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.utils import to_collection
from pydantic import BaseModel, computed_field, model_validator, BeforeValidator, Field, DirectoryPath, PrivateAttr

from musify_cli.exception import ParserError
from musify_cli.parser.library import LibraryConfig
from musify_cli.parser.operations.signature import get_default_args
from musify_cli.parser.operations.tagger import Tagger
from musify_cli.parser.operations.tags import LocalTrackFields, LOCAL_TRACK_TAG_NAMES

LOCAL_LIBRARY_TYPES = {cls.source.lower() for cls in LIBRARY_CLASSES}


class LocalLibraryPathsParser[T: Path | tuple[Path, ...] | None](BaseModel, metaclass=ABCMeta):
    """Base class for parsing and validating library paths config, giving platform appropriate paths."""
    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def _platform_key(cls) -> str:
        platform_map = {"win32": "win", "linux": "lin", "darwin": "mac"}
        return platform_map[sys.platform]

    @computed_field(
        description="The source type of the library associated with these paths",
    )
    @property
    @abstractmethod
    def source(self) -> str:
        """The source type of the library associated with these paths"""
        raise NotImplementedError

    @computed_field(
        description="The paths configured for the current platform",
    )
    @property
    def paths(self) -> T:
        """The path/s configured for the current platform"""
        return self.__getattribute__(self._platform_key)

    @model_validator(mode="after")
    def validate_path_exists(self) -> Self:
        if not self.paths:
            raise ParserError(
                f"No valid paths found for the current platform: {self._platform_key}",
                value=self.paths,
            )

        return self

    @computed_field(
        description="The paths configured for platforms that are not the current platform",
    )
    @property
    def others(self) -> list[Path]:
        """The path/s configured for platforms that are not the current platform"""
        return [
            path
            for key in self.__annotations__ if key != self._platform_key and self.__getattribute__(key) is not None
            for path in to_collection(self.__getattribute__(key))
        ]


class LocalLibraryPaths(LocalLibraryPathsParser[tuple[Path, ...]]):
    """Parses and validates library paths for a :py:class:`LocalLibrary`, giving platform appropriate paths."""
    win: Annotated[tuple[PureWindowsPath, ...], BeforeValidator(to_collection)] | None = Field(
        description="The windows path/s for the MusicBee library",
        default=()
    )
    lin: Annotated[tuple[PurePosixPath, ...], BeforeValidator(to_collection)] | None = Field(
        description="The linux path/s for the MusicBee library",
        default=()
    )
    mac: Annotated[tuple[PurePosixPath, ...], BeforeValidator(to_collection)] | None = Field(
        description="The mac path/s for the MusicBee library",
        default=()
    )

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def source(cls) -> str:
        return str(LocalLibrary.source)

    @model_validator(mode="after")
    def validate_path_is_dir(self) -> Self:
        if not all(Path(path).is_dir() for path in self.paths):
            raise ParserError(
                "The paths given for the current platform are not valid directories",
                value=self.paths,
            )

        return self


class MusicBeePaths(LocalLibraryPathsParser[Path]):
    """Parses and validates library paths for a :py:class:`MusicBee` library, giving platform appropriate paths."""
    win: PureWindowsPath | None = Field(
        description="The windows path for the MusicBee library",
        default=None
    )
    lin: PurePosixPath | None = Field(
        description="The linux path for the MusicBee library",
        default=None
    )
    mac: PurePosixPath | None = Field(
        description="The mac path for the MusicBee library",
        default=None
    )

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def source(cls) -> str:
        return str(MusicBee.source)

    @model_validator(mode="after")
    def validate_path_is_musicbee_lib(self) -> Self:
        if not (path := Path(self.paths).joinpath(MusicBee.xml_library_path)).is_file():
            raise ParserError(
                "No MusicBee library found at the given path",
                value=path,
            )
        if not (path := Path(self.paths).joinpath(MusicBee.xml_settings_path)).is_file():
            raise ParserError(
                "No MusicBee settings found at the given path",
                value=path,
            )

        return self


local_library_defaults = get_default_args(LocalLibrary)


class LocalPaths[T: LocalLibraryPathsParser](BaseModel):
    library: DirectoryPath | list[DirectoryPath] | T = Field(
        description="The path/s for the library folder/s. May be defined as a single path, list of paths, "
                    "or a map with platform specific keys relating to the library path/s for that platform. "
                    f"Recognised platform keys: {tuple(LocalLibraryPaths.__annotations__)}"
    )
    playlists: DirectoryPath | list[DirectoryPath] | None = Field(
        description="The path of the playlist folder",
        default=local_library_defaults.get("playlist_folder")
    )
    map: dict[str, str] = Field(
        description="A map of stems to be used as part of the PathStemMapper",
        default_factory=dict
    )

    @model_validator(mode="after")
    def extend_stem_map_with_other_platforms(self) -> Self:
        if not isinstance(self.library, LocalLibraryPathsParser):
            return self

        if self.map is None:
            self.map = {}

        actual_path = str(next(iter(to_collection(self.library.paths))))
        other_paths = map(str, self.library.others)
        self.map.update({other_path: actual_path for other_path in other_paths if other_path != actual_path})

        return self


updater_defaults = get_default_args(LocalTrack.save)


class UpdaterConfig(BaseModel):
    tags: LocalTrackFields = Field(
        description=f"The tags to be updated. Accepted tags: {LOCAL_TRACK_TAG_NAMES}",
        default=updater_defaults.get("tags", LocalTrackField.ALL)
    )
    replace: bool = Field(default=updater_defaults.get("replace", False))


class TagsConfig(BaseModel):
    rules: Tagger = Field(
        description="The auto-tagger rules",
        default=Tagger(),
    )


class LocalLibraryConfig[T: LocalLibraryPathsParser](LibraryConfig):
    # noinspection PyUnboundLocalVariable
    _type_map: dict[str, Type[LocalLibraryPathsParser]] = PrivateAttr(default={
        "local": LocalLibraryPaths,
        "musicbee": MusicBeePaths,
    })

    # noinspection PyTypeChecker
    paths: LocalPaths[T] = Field(
        description="Configuration for the paths of this local library"
    )
    updater: UpdaterConfig = Field(
        description="Options for tag update operations",
        default=UpdaterConfig()
    )
    tags: TagsConfig = Field(
        description="Options for automatically tagging tracks based on a set of user-defined rules",
        default=TagsConfig()
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def extract_type_from_input(cls, data: Any) -> Any:
        """Attempt to infer and set the ``type`` field from the other input fields"""
        if not isinstance(data, MutableMapping):
            return data

        if (
                isinstance((paths := data.get("paths")), LocalPaths)
                and isinstance((library := paths.library), LocalLibraryPathsParser)
        ):
            data["type"] = library.source

        return data

    @model_validator(mode="after")
    def extract_library_paths(self) -> Self:
        if isinstance(self.paths.library, LocalLibraryPathsParser):
            self.paths.library = self.paths.library.paths
        return self
