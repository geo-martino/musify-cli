import sys
from abc import ABCMeta, abstractmethod
from pathlib import Path, PureWindowsPath, PurePosixPath, PurePath
from typing import Self, ClassVar, Annotated

from aiorequestful.types import UnitCollection
from musify.file.path_mapper import PathMapper, PathStemMapper
from musify.libraries.local.collection import LocalCollection, BasicLocalCollection
from musify.libraries.local.library import LocalLibrary, MusicBee
from musify.libraries.local.track import LocalTrack, SyncResultTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.utils import classproperty, to_collection
from pydantic import BaseModel, computed_field, model_validator, BeforeValidator, Field, DirectoryPath, ConfigDict

from musify_cli.config.library._core import LibraryConfig, Instantiator, Runner
from musify_cli.config.operations.signature import get_default_args
from musify_cli.config.operations.tagger import Tagger
from musify_cli.config.operations.tags import LocalTrackFields, LOCAL_TRACK_TAG_NAMES
from musify_cli.exception import ParserError


class LocalLibraryPathsParser[T: Path | tuple[Path, ...] | None](BaseModel, metaclass=ABCMeta):
    """Base class for parsing and validating library paths config, giving platform appropriate paths."""
    model_config = ConfigDict(ignored_types=(classproperty,))

    # noinspection PyMethodParameters
    @classproperty
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
        paths = self.__getattribute__(self._platform_key)
        if not paths:
            return paths

        if isinstance(paths, PurePath):
            return Path(paths)
        return tuple(map(Path, paths))

    @model_validator(mode="after")
    def validate_path_exists(self) -> Self:
        """Ensure paths are configured for the current platform"""
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

    # noinspection PyMethodParameters
    @classproperty
    def source(cls) -> str:
        return str(LocalLibrary.source)

    @model_validator(mode="after")
    def validate_path_is_dir(self) -> Self:
        """Ensure the configured paths are directories"""
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

    # noinspection PyMethodParameters
    @classproperty
    def source(cls) -> str:
        return str(MusicBee.source)

    @model_validator(mode="after")
    def validate_path_is_musicbee_lib(self) -> Self:
        """Ensure the configured path points to a valid MusicBee library folder"""
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


class LocalPaths[T: LocalLibraryPathsParser](Instantiator[PathMapper]):
    library: DirectoryPath | list[DirectoryPath] | T = Field(
        description="The path/s for the library folder/s. May be defined as a single path, list of paths, "
                    "or a map with platform specific keys relating to the library path/s for that platform. "
                    f"Recognised platform keys: {tuple(LocalLibraryPaths.__annotations__)}"
    )
    playlists: DirectoryPath | None = Field(
        description="The path of the playlist folder",
        default=local_library_defaults.get("playlist_folder")
    )
    map: dict[str, str] = Field(
        description="A map of stems to be used as part of the PathStemMapper",
        default_factory=dict
    )

    @model_validator(mode="after")
    def extend_stem_map_with_other_platforms(self) -> Self:
        """Extend the map with paths for other platforms"""
        if not isinstance(self.library, LocalLibraryPathsParser):
            return self

        if self.map is None:
            self.map = {}

        actual_path = str(next(iter(to_collection(self.library.paths))))
        other_paths = map(str, self.library.others)
        self.map.update({other_path: actual_path for other_path in other_paths if other_path != actual_path})

        return self

    def create(self):
        return PathStemMapper(stem_map=self.map)


updater_defaults = get_default_args(LocalTrack.save)


class UpdaterConfig(Runner[dict[LocalTrack, SyncResultTrack]]):
    tags: LocalTrackFields = Field(
        description=f"The tags to be updated. Accepted tags: {LOCAL_TRACK_TAG_NAMES}",
        default=updater_defaults.get("tags", LocalTrackField.ALL)
    )
    replace: bool = Field(default=updater_defaults.get("replace", False))

    async def run(self, collection: UnitCollection[LocalCollection], dry_run: bool = True):
        """
        Saves the tags of all tracks in the given ``collection``.

        :param collection: The collection/s containing the tracks which you wish to save.
        :param dry_run: Run function, but do not modify the files on the disk.
        :return: A map of the :py:class:`LocalTrack` saved to its result as a :py:class:`SyncResultTrack` object
        """
        if isinstance(collection, LocalCollection):
            item_log = f"{len(collection)} tracks"
        else:  # flatten many collections to one
            item_log = f"{sum(len(coll) for coll in collection)} tracks in {len(collection)} collections"
            collection = BasicLocalCollection(name="saver", tracks=[track for coll in collection for track in coll])

        self._logger.info(
            f"\33[1;95m ->\33[1;97m Updating tags for {item_log}: "
            f"\33[0;90m{', '.join(t.name.lower() for t in to_collection(self.tags))}\33[0m"
        )

        return await collection.save_tracks(tags=self.tags, replace=self.replace, dry_run=dry_run)


class TagsConfig(Runner[dict[LocalTrack, SyncResultTrack]]):
    rules: Tagger = Field(
        description="The auto-tagger rules",
        default_factory=Tagger,
    )

    async def run(self, library: LocalLibrary, updater: UpdaterConfig = None, dry_run: bool = True):
        """
        Set the tags for the tracks in the given library based on set rules.

        :param library: The library containing tracks to be processed
        :param updater: If given, update the track files on the disk with the updated tags
        :param dry_run: Run function, but do not modify the files on the disk. Only used if an ``updater`` is given.
        :return: A map of the :py:class:`LocalTrack` saved to its result as a :py:class:`SyncResultTrack` object
        """
        if not self.rules.rules:
            return {}

        self._logger.info(f"\33[1;95m ->\33[1;97m Setting tags for {len(library)} tracks\33[0m")
        self.rules.set_tags(library, library.folders)
        if updater is None:
            return {}

        return await updater(collection=library, dry_run=dry_run)


class LocalLibraryConfig[L: LocalLibrary, P: LocalLibraryPathsParser](LibraryConfig[L]):

    _library_cls: ClassVar[type[LocalLibrary]] = LocalLibrary

    # noinspection PyTypeChecker
    paths: LocalPaths[P] = Field(
        description="Configuration for the paths of this local library"
    )
    updater: UpdaterConfig = Field(
        description="Options for tag update operations",
        default_factory=UpdaterConfig,
    )
    tags: TagsConfig = Field(
        description="Options for automatically tagging tracks based on a set of user-defined rules",
        default_factory=TagsConfig,
    )

    @model_validator(mode="after")
    def extract_library_paths(self) -> Self:
        """Set the current platform's paths as the library paths when multiple platforms are configured."""
        if isinstance(self.paths.library, LocalLibraryPathsParser):
            self.paths.library = self.paths.library.paths
        return self

    def create(self, wrangler: RemoteDataWrangler = None):
        return self._library_cls(
            library_folders=self.paths.library,
            playlist_folder=self.paths.playlists,
            playlist_filter=self.playlists.filter,
            path_mapper=self.paths.create(),
            remote_wrangler=wrangler,
        )

    # noinspection PyMethodParameters
    @classproperty
    def source(cls) -> str:
        """The source type of the library"""
        return str(cls._library_cls.source)


class MusicBeeConfig(LocalLibraryConfig[MusicBee, MusicBeePaths]):

    _library_cls: ClassVar[type[MusicBee]] = MusicBee

    # noinspection PyMethodParameters
    @classproperty
    def source(cls) -> str:
        """The source type of the library"""
        return str(cls._library_cls.source)

    def create(self, wrangler: RemoteDataWrangler | None = None):
        return self._library_cls(
            musicbee_folder=self.paths.library,
            playlist_filter=self.playlists.filter,
            path_mapper=self.paths.create(),
            remote_wrangler=wrangler,
        )


LOCAL_LIBRARY_CONFIG: frozenset[type[LocalLibraryConfig]] = frozenset({
    LocalLibraryConfig[LocalLibrary, LocalLibraryPaths], MusicBeeConfig,
})
