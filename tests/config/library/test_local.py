from collections.abc import Collection
from copy import deepcopy
from pathlib import Path, PureWindowsPath, PurePosixPath
from random import choice, randrange
from typing import Any

import pytest
from musify.file.path_mapper import PathStemMapper
from musify.libraries.local.collection import BasicLocalCollection, LocalCollection
from musify.libraries.local.library import MusicBee, LocalLibrary
from musify.libraries.local.track.field import LocalTrackField
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from musify.utils import to_collection
from pydantic import ValidationError

from mocks.local import LocalLibraryMock, LocalTrackMock
from musify_cli.config.library.local import LOCAL_LIBRARY_CONFIG, LocalLibraryPathsParser, LocalPaths, \
    LocalLibraryPaths, MusicBeePaths, LocalLibraryConfig, MusicBeeConfig, UpdaterConfig, TagsConfig
from musify_cli.config.operations.tagger import FilteredSetter
# noinspection PyProtectedMember
from musify_cli.config.operations.tagger._setter import Value
from utils import random_str, random_tracks


class TestLocalLibraryPaths:

    paths = dict(
        win=(r"C:\windows\path1", r"C:\windows\path2"),
        lin=["/linux/path1", "/linux/path2"],
        mac={"/mac/path1", "/mac/path2"},
    )

    @classmethod
    def get_valid_paths(cls, tmp_path: Path) -> dict[str, Collection[str]]:
        paths = deepcopy(cls.paths)
        paths[str(LocalLibraryPathsParser._platform_key)] = [str(tmp_path)]
        return paths

    @pytest.fixture
    def valid_paths(self, tmp_path: Path) -> dict[str, Collection[str]]:
        return self.get_valid_paths(tmp_path)

    @pytest.fixture
    def invalid_paths(self) -> dict[str, Collection[str]]:
        return deepcopy(self.paths)

    @pytest.fixture
    def valid_model(self, valid_paths: dict[str, Collection[str]]) -> LocalLibraryPaths:
        return LocalLibraryPaths(**valid_paths)

    # noinspection PyStatementEffect
    def test_init_fails(self, invalid_paths: dict[str, Collection[str]]):
        with pytest.raises(ValidationError, match="are not valid directories"):
            LocalLibraryPaths(**invalid_paths)

        invalid_paths.pop(str(LocalLibraryPathsParser._platform_key))
        with pytest.raises(ValidationError, match="No valid paths found for the current platform"):
            LocalLibraryPaths(**invalid_paths)

    def test_properties(self, valid_model: LocalLibraryPaths):
        assert valid_model.source == LocalLibrary.source

    def test_parameters(self, valid_model: LocalLibraryPaths, valid_paths: dict[str, Collection[str]]):
        assert valid_model.win == tuple(PureWindowsPath(path) for path in valid_paths["win"])
        assert valid_model.lin == tuple(PurePosixPath(path) for path in valid_paths["lin"])
        assert valid_model.mac == tuple(PurePosixPath(path) for path in valid_paths["mac"])

        assert valid_model.paths == tuple(Path(path) for path in valid_paths[str(valid_model._platform_key)])
        assert all(path not in valid_model.paths for path in valid_model.others)

    def test_properties_on_unit_path(self, valid_paths: dict[str, Collection[str]]):
        paths = {k: next(iter(v)) for k, v in valid_paths.items()}
        model = LocalLibraryPaths(**paths)

        assert isinstance(model.win, tuple)
        assert isinstance(model.lin, tuple)
        assert isinstance(model.mac, tuple)


class TestMusicBeePaths:

    paths = dict(
        win=r"C:\windows\path",
        lin="/linux/path",
        mac="/mac/path",
    )

    @classmethod
    def get_valid_paths(cls, musicbee_folder: Path) -> dict[str, str]:
        paths = deepcopy(cls.paths)
        paths[str(MusicBeePaths._platform_key)] = str(musicbee_folder)
        return paths

    @pytest.fixture
    def valid_paths(self, musicbee_folder: Path) -> dict[str, str]:
        return self.get_valid_paths(musicbee_folder)

    @pytest.fixture
    def invalid_paths(self) -> dict[str, Collection[str]]:
        return deepcopy(self.paths)

    @pytest.fixture
    def valid_model(self, valid_paths: dict[str, str]) -> MusicBeePaths:
        return MusicBeePaths(**valid_paths)

    def test_properties(self, valid_model: MusicBeePaths):
        assert valid_model.source == MusicBee.source

    def test_parameters(self, valid_model: MusicBeePaths, valid_paths: dict[str, str]):
        assert valid_model.win == PureWindowsPath(valid_paths["win"])
        assert valid_model.lin == PurePosixPath(valid_paths["lin"])
        assert valid_model.mac == PurePosixPath(valid_paths["mac"])

        assert valid_model.paths == Path(valid_paths[str(valid_model._platform_key)])
        assert all(path != valid_model.paths for path in valid_model.others)

    def test_get_paths_fails(self, invalid_paths: dict[str, str]):
        with pytest.raises(ValidationError, match="No MusicBee library found"):
            MusicBeePaths(**invalid_paths)

        invalid_paths.pop(str(LocalLibraryPathsParser._platform_key))
        with pytest.raises(ValidationError, match="No valid paths found for the current platform"):
            MusicBeePaths(**invalid_paths)


class TestLocalPaths:
    @pytest.fixture(params=LOCAL_LIBRARY_CONFIG)
    def model_type(self, request) -> type[LocalLibraryConfig]:
        return request.param

    @pytest.fixture
    def library_paths_type(self, model_type: type[LocalLibraryConfig]) -> type[LocalLibraryPathsParser]:
        type_map = {
            LocalLibraryConfig.source: LocalLibraryPaths,
            MusicBeeConfig.source: MusicBeePaths,
        }
        return type_map[model_type.source]

    @pytest.fixture
    def library_paths(
            self, model_type: type[LocalLibraryConfig], tmp_path: Path, musicbee_folder: Path
    ) -> dict[str, Any]:
        paths_map = {
            LocalLibraryConfig.source: TestLocalLibraryPaths.get_valid_paths(tmp_path),
            MusicBeeConfig.source: TestMusicBeePaths.get_valid_paths(musicbee_folder),
        }
        return paths_map[model_type.source]

    @pytest.fixture
    def model(
            self, library_paths: dict[str, Any], library_paths_type: type[LocalLibraryPathsParser]
    ) -> LocalPaths:
        return LocalPaths[library_paths_type](library=library_paths)

    def test_updates_map_with_other_platform_paths(self, model: LocalPaths, library_paths: dict[str, Any]):
        assert len(model.map) >= len(library_paths) - 1

        expected_path = next(iter(to_collection(library_paths[str(LocalLibraryPathsParser._platform_key)])))
        library_paths = [
            path for key, paths in library_paths.items() for path in to_collection(paths)
            if key != str(LocalLibraryPathsParser._platform_key)
        ]
        for path in library_paths:
            assert model.map[path] == expected_path

    def test_create(self, model: LocalPaths):
        assert model.map

        path_mapper = model.create()
        assert isinstance(path_mapper, PathStemMapper)
        assert path_mapper.stem_map == model.map


class TestUpdater:
    @pytest.fixture
    def model(self) -> UpdaterConfig:
        return UpdaterConfig(
            tags=["album", "album_artist", "track", "disc", "compilation"],
            replace=choice([True, False]),
        )

    @pytest.fixture
    def library(self, collections: list[LocalCollection[LocalTrackMock]]) -> LocalLibraryMock:
        library = LocalLibraryMock()
        # noinspection PyTestUnpassedFixture
        library._tracks = [track for collection in collections for track in collection]
        return library

    @pytest.fixture
    def collections(self) -> list[LocalCollection[LocalTrackMock]]:
        return [
            BasicLocalCollection[LocalTrackMock](name=random_str(), tracks=random_tracks(cls=LocalTrackMock))
            for _ in range(randrange(3, 10))
        ]

    @staticmethod
    def assert_save_library(model: UpdaterConfig, library: LocalLibraryMock, dry_run: bool):
        assert library.save_tracks_args["tags"] == model.tags
        assert library.save_tracks_args["replace"] == model.replace
        assert library.save_tracks_args["dry_run"] == dry_run

    @classmethod
    def assert_save_collections(
            cls, model: UpdaterConfig, collections: Collection[Collection[LocalTrackMock]], dry_run: bool
    ):
        for collection in collections:
            cls.assert_save_tracks(model=model, tracks=collection, dry_run=dry_run)

    @staticmethod
    def assert_save_tracks(model: UpdaterConfig, tracks: Collection[LocalTrackMock], dry_run: bool):
        for track in tracks:
            assert track.save_args["tags"] == model.tags
            assert track.save_args["replace"] == model.replace
            assert track.save_args["dry_run"] == dry_run

    @pytest.mark.parametrize("dry_run", [True, False])
    async def test_save_library(self, model: UpdaterConfig, library: LocalLibraryMock, dry_run: bool):
        await model.run(collection=library, dry_run=dry_run)
        self.assert_save_library(model=model, library=library, dry_run=dry_run)

    @pytest.mark.parametrize("dry_run", [True, False])
    async def test_save_collections(
            self, model: UpdaterConfig, collections: list[LocalCollection[LocalTrackMock]], dry_run: bool
    ):
        await model.run(collection=collections, dry_run=dry_run)
        self.assert_save_collections(model=model, collections=collections, dry_run=dry_run)


class TestTags:

    @pytest.fixture
    def fields(self) -> list[LocalTrackField]:
        return LocalTrackField.from_name(*("album", "album_artist", "title", "artist"))

    @pytest.fixture
    def model(self, fields: list[LocalTrackField]) -> TagsConfig:
        setters = [Value(field=field, value=random_str()) for field in fields]
        return TagsConfig(rules=[FilteredSetter(setters=setters)])

    @pytest.fixture
    def updater(self, fields: list[LocalTrackField]) -> UpdaterConfig:
        return UpdaterConfig(tags=fields, replace=choice([True, False]))

    @pytest.fixture
    def library(self, collections: list[LocalCollection[LocalTrackMock]]) -> LocalLibraryMock:
        library = LocalLibraryMock()
        # noinspection PyTestUnpassedFixture
        library._tracks = [track for collection in collections for track in collection]
        return library

    @pytest.fixture
    def collections(self) -> list[LocalCollection[LocalTrackMock]]:
        return [
            BasicLocalCollection[LocalTrackMock](name=random_str(), tracks=random_tracks(cls=LocalTrackMock))
            for _ in range(randrange(3, 10))
        ]

    @staticmethod
    def assert_tags_set(model: TagsConfig, tracks: Collection[LocalTrackMock]):
        # noinspection PyTypeChecker
        setters: list[Value] = [setter for rule in model.rules.rules for setter in rule.setters]
        for setter in setters:
            for track in tracks:
                assert track[setter.field] == setter.value

    async def test_set_no_tags_on_no_rules(self, model: TagsConfig, library: LocalLibraryMock):
        # noinspection PyTypeChecker
        setters: list[Value] = [setter for rule in model.rules.rules for setter in rule.setters]

        model.rules.rules = []
        assert not await model.run(library)

        for setter in setters:
            for track in library:
                # noinspection PyTestUnpassedFixture
                assert track[setter.field] != setter.value

    async def test_set_tags_no_updater(self, model: TagsConfig, library: LocalLibraryMock):
        assert not await model.run(library)
        self.assert_tags_set(model, tracks=library)

    @pytest.mark.parametrize("dry_run", [True, False])
    async def test_set_tags_with_updater(
            self, model: TagsConfig, updater: UpdaterConfig, library: LocalLibraryMock, dry_run: bool
    ):
        await model.run(library, updater=updater, dry_run=dry_run)
        self.assert_tags_set(model, tracks=library)
        TestUpdater.assert_save_library(model=updater, library=library, dry_run=dry_run)


class TestLocalLibraryConfig:

    @pytest.fixture
    def library_paths(self, tmp_path: Path) -> dict[str, Any]:
        return TestLocalLibraryPaths.get_valid_paths(tmp_path)

    @pytest.fixture
    def model(self, library_paths: dict[str, Any], tmp_path: Path) -> LocalLibraryConfig:
        return LocalLibraryConfig[LocalLibrary, LocalLibraryPaths](
            name=random_str(), paths={"library": library_paths, "playlists": tmp_path}
        )

    @pytest.fixture
    def library_paths_model(self, library_paths: dict[str, Any]) -> LocalPaths:
        return LocalLibraryPaths(**library_paths)

    def test_properties(self, model: LocalLibraryConfig):
        assert model.source == LocalLibrary.source

    def test_assigns_library_paths(
            self, model: LocalLibraryConfig, library_paths_model: LocalLibraryPathsParser
    ):
        assert model.paths.library == library_paths_model.paths

    def test_create(self, model: LocalLibraryConfig):
        assert model.paths.library
        assert model.paths.playlists

        wrangler = SpotifyDataWrangler()
        library = model.create(wrangler)
        assert isinstance(library, LocalLibrary)

        assert library.library_folders == to_collection(model.paths.library, list)
        assert library.playlist_folder == model.paths.playlists

        assert id(library.playlist_filter) == id(model.playlists.filter)
        assert isinstance(library.path_mapper, PathStemMapper)
        assert library.path_mapper.stem_map == model.paths.map
        assert library.remote_wrangler.source == wrangler.source


class TestMusicBeeConfig(TestLocalLibraryConfig):

    @pytest.fixture
    def library_paths(self, musicbee_folder: Path) -> dict[str, Any]:
        return TestMusicBeePaths.get_valid_paths(musicbee_folder)

    @pytest.fixture
    def model(self, library_paths: dict[str, Any], tmp_path: Path) -> LocalLibraryConfig:
        return MusicBeeConfig(name=random_str(), paths={"library": library_paths, "playlists": tmp_path})

    @pytest.fixture
    def library_paths_model(self, library_paths: dict[str, Any]) -> LocalPaths:
        return MusicBeePaths(**library_paths)

    def test_properties(self, model: LocalLibraryConfig):
        assert model.source == MusicBee.source

    def test_create(self, model: LocalLibraryConfig):
        assert model.paths.library
        assert model.paths.playlists

        wrangler = SpotifyDataWrangler()
        library = model.create(wrangler)
        assert isinstance(library, MusicBee)

        # noinspection PyTestUnpassedFixture
        assert library.musicbee_folder == model.paths.library
        assert id(library.playlist_filter) == id(model.playlists.filter)
        assert isinstance(library.path_mapper, PathStemMapper)
        assert library.path_mapper.stem_map == model.paths.map
        assert library.remote_wrangler.source == wrangler.source
