from collections.abc import Generator, Collection, Iterable
from copy import deepcopy
from pathlib import Path
from typing import get_args
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from mytunes.core.collection import SYNC_TYPE
from mytunes.core.playlist import Playlist
from mytunes.local.library import LocalLibrary
from mytunes.local.playlist import M3U, LocalPlaylist
from pytest_mock import MockerFixture

from mytunes_cli.operations.playlist.core import SyncLocalAndRemotePlaylists, SyncLocalPlaylists, ExportLocalPlaylists
from mytunes_cli.state import GlobalState
from tests.operations.testers import OperationTester


class TestExportLocalPlaylists(OperationTester):
    @pytest.fixture
    def model(
            self, state: GlobalState, local_library_name: str, tmp_path: Path, faker: Faker
    ) -> ExportLocalPlaylists:
        state = state.model_copy(update=dict(dry_run=False))
        return ExportLocalPlaylists(state=state, library_name=local_library_name, path=tmp_path)

    @pytest.fixture
    def playlists(self, playlists: list[Playlist], faker: Faker) -> list[LocalPlaylist]:
        return [
            M3U(**pl.model_dump(), path=Path(faker.file_path(extension=".m3u")).with_name(pl.name))
            for pl in playlists
        ]

    @pytest.fixture
    def mock_playlists(
            self, model: ExportLocalPlaylists, playlists: list[Playlist], mocker: MockerFixture
    ) -> Generator[Mock]:
        model.library.playlists.extend(playlists)

        mock_playlists = mocker.spy(model, "_get_playlists")
        yield mock_playlists
        mock_playlists.assert_called_once_with(model.library)

    async def test_run(
            self,
            model: ExportLocalPlaylists,
            playlists: list[LocalPlaylist],
            mock_playlists: Mock,
            mocker: MockerFixture,
    ):
        mock_save = mocker.spy(M3U, "save")

        await model.run()

        assert mock_save.call_count == len(playlists)
        assert mock_save.call_args.kwargs["dry_run"] is False

        assert all(not pl.path.exists() for pl in playlists)
        assert len(set(model.output_dir.rglob("*.m3u"))) == len(playlists)


class TestSyncLocalPlaylists(OperationTester):
    @pytest.fixture
    def model(
            self, state: GlobalState, local_libraries: dict[str, LocalLibrary], faker: Faker
    ) -> SyncLocalPlaylists:
        source, target, reference = faker.random_elements(list(local_libraries), length=3, unique=True)
        return SyncLocalPlaylists(
            state=state,
            source_name=source,
            target_name=target,
            reference_name=reference,
        )

    @pytest.fixture
    def playlists(self, playlists: list[Playlist], tmp_path: Path, faker: Faker) -> list[LocalPlaylist]:
        return [
            M3U(
                **pl.model_dump(),
                path=Path(*faker.words()).with_stem(pl.name).with_suffix("." + next(iter(M3U.__supported_extensions__)))
            )
            for pl in playlists
        ]

    @pytest.fixture(autouse=True)
    def source_playlists(
            self, model: SyncLocalPlaylists, playlists: list[LocalPlaylist], tmp_path: Path, faker: Faker
    ) -> list[LocalPlaylist]:
        return self._setup_playlists_on_library(model.source, playlists, tmp_path, faker)

    @pytest.fixture(autouse=True)
    def target_playlists(
            self, model: SyncLocalPlaylists, playlists: list[LocalPlaylist], tmp_path: Path, faker: Faker
    ) -> list[LocalPlaylist]:
        return self._setup_playlists_on_library(model.target, playlists, tmp_path, faker)

    @pytest.fixture(autouse=True)
    def reference_playlists(
            self, model: SyncLocalPlaylists, playlists: list[LocalPlaylist], tmp_path: Path, faker: Faker
    ) -> list[LocalPlaylist]:
        return self._setup_playlists_on_library(model.reference, playlists, tmp_path, faker)

    @staticmethod
    def _setup_playlists_on_library(
            library: LocalLibrary, playlists: list[LocalPlaylist], tmp_path: Path, faker: Faker
    ) -> list[LocalPlaylist]:
        playlist_folder = tmp_path / Path(*faker.words())
        playlists = deepcopy(playlists)
        for playlist in playlists:
            playlist.path = playlist_folder.joinpath(playlist.path)
            playlist.path.parent.mkdir(parents=True, exist_ok=True)
            playlist.path.touch()

        library.playlist_folder = playlist_folder
        library.playlists.replace(playlists)
        return playlists

    @pytest.fixture
    def source_playlists_removed(
            self, model: SyncLocalPlaylists, source_playlists: list[LocalPlaylist], faker: Faker,
    ) -> list[LocalPlaylist]:
        return self._remove_playlist_from_library(model.source, source_playlists, faker)

    @pytest.fixture
    def target_playlists_removed(
            self, model: SyncLocalPlaylists, target_playlists: list[LocalPlaylist], faker: Faker,
    ) -> list[LocalPlaylist]:
        return self._remove_playlist_from_library(model.target, target_playlists, faker)

    @staticmethod
    def _remove_playlist_from_library(library: LocalLibrary, playlists: list[LocalPlaylist], faker: Faker):
        removed_count = faker.random_int(1, len(playlists) // 3)
        removed = faker.random_elements(playlists, length=removed_count, unique=True)
        for pl in removed:
            library.playlists.remove(pl)
            playlists.remove(pl)

        return list(removed)

    def test_normalise_playlist_paths(self, model: SyncLocalPlaylists, playlists: list[Playlist]):
        for playlist in list(model.source.playlists.unique) + list(model.target.playlists.unique):
            assert playlist.path.is_absolute()

        with model._normalise_playlist_paths(model.source, model.target):
            for playlist in list(model.source.playlists.unique) + list(model.target.playlists.unique):
                assert not playlist.path.is_absolute()

        for playlist in list(model.source.playlists.unique) + list(model.target.playlists.unique):
            assert playlist.path.is_absolute()

    @staticmethod
    def get_expected_relative_paths(model: SyncLocalPlaylists) -> set[Path]:
        """This needs to be called once paths are normalised to produce a valid result."""
        source_paths = {pl.path for pl in model.source.playlists.unique}
        target_paths = {pl.path for pl in model.target.playlists.unique}
        reference_paths = {pl.path for pl in model.reference.playlists.unique}

        expected_paths = (source_paths | target_paths) - (reference_paths - source_paths & target_paths)
        assert expected_paths != source_paths | target_paths | reference_paths

        return expected_paths

    @staticmethod
    def assert_playlists_exist(playlists: Iterable[LocalPlaylist]) -> None:
        for pl in playlists:
            print(pl.path)
            assert pl.path.is_file()

    @staticmethod
    def assert_playlists_removed(
            library: LocalLibrary, playlists: Iterable[LocalPlaylist], expected: Collection[Path]
    ) -> None:
        assert all(pl.path.relative_to(library.playlist_folder).with_suffix("") in expected for pl in library.playlists)
        assert all(pl.path.relative_to(library.playlist_folder).with_suffix("") in expected for pl in playlists)

    @staticmethod
    def assert_playlists_deleted(
            library: LocalLibrary, playlists: Iterable[LocalPlaylist], expected: Collection[Path]
    ) -> None:
        for pl in playlists:
            if pl.path.relative_to(library.playlist_folder).with_suffix("") not in expected:
                assert not pl.path.exists()

    def test_remove_playlists(
            self,
            model: SyncLocalPlaylists,
            source_playlists: list[LocalPlaylist],
            source_playlists_removed: list[LocalPlaylist],
            target_playlists: list[LocalPlaylist],
            target_playlists_removed: list[LocalPlaylist],
            reference_playlists: list[LocalPlaylist],
    ):
        model.state = model.state.model_copy(update=dict(dry_run=False))

        self.assert_playlists_exist(model.source.playlists.unique)
        self.assert_playlists_exist(model.target.playlists.unique)
        self.assert_playlists_exist(model.reference.playlists.unique)

        with model._normalise_playlist_paths(model.source, model.target, model.reference):
            expected_paths = self.get_expected_relative_paths(model)
            model._remove_playlists(source_playlists, target_playlists, reference_playlists)

        self.assert_playlists_removed(model.source, source_playlists, expected_paths)
        self.assert_playlists_removed(model.target, target_playlists, expected_paths)
        self.assert_playlists_removed(model.reference, reference_playlists, expected_paths)

        self.assert_playlists_deleted(model.source, source_playlists, expected_paths)
        self.assert_playlists_deleted(model.target, target_playlists, expected_paths)
        self.assert_playlists_deleted(model.reference, reference_playlists, expected_paths)

    def test_remove_playlists_dry_run(
            self,
            model: SyncLocalPlaylists,
            source_playlists: list[LocalPlaylist],
            source_playlists_removed: list[LocalPlaylist],
            target_playlists: list[LocalPlaylist],
            target_playlists_removed: list[LocalPlaylist],
            reference_playlists: list[LocalPlaylist],
    ):
        model.state = model.state.model_copy(update=dict(dry_run=True))

        self.assert_playlists_exist(model.source.playlists.unique)
        self.assert_playlists_exist(model.target.playlists.unique)
        self.assert_playlists_exist(model.reference.playlists.unique)

        with model._normalise_playlist_paths(model.source, model.target, model.reference):
            expected_paths = self.get_expected_relative_paths(model)
            model._remove_playlists(source_playlists, target_playlists, reference_playlists)

        self.assert_playlists_removed(model.source, source_playlists, expected_paths)
        self.assert_playlists_removed(model.target, target_playlists, expected_paths)
        self.assert_playlists_removed(model.reference, reference_playlists, expected_paths)

        self.assert_playlists_exist(model.source.playlists.unique)
        self.assert_playlists_exist(model.target.playlists.unique)
        self.assert_playlists_exist(model.reference.playlists.unique)

    def test_remove_playlists_skips_added(
            self,
            model: SyncLocalPlaylists,
            source_playlists: list[LocalPlaylist],
            source_playlists_removed: list[LocalPlaylist],
            target_playlists: list[LocalPlaylist],
            target_playlists_removed: list[LocalPlaylist],
            reference_playlists: list[LocalPlaylist],
            faker: Faker
    ):
        # we remove some playlists from the reference to simulate playlists added in other libraries
        for pl in faker.random_elements(reference_playlists, length=2, unique=True):
            model.reference.playlists.remove(pl)
            reference_playlists.remove(pl)

        with model._normalise_playlist_paths(model.source, model.target, model.reference):
            expected_paths = self.get_expected_relative_paths(model)
            model._remove_playlists(source_playlists, target_playlists, reference_playlists)

        self.assert_playlists_removed(model.source, source_playlists, expected_paths)
        self.assert_playlists_removed(model.target, target_playlists, expected_paths)
        self.assert_playlists_removed(model.reference, reference_playlists, expected_paths)

    @pytest.fixture
    def mock_playlists(self, model: SyncLocalPlaylists, mocker: MockerFixture) -> Generator[Mock]:
        mock_playlists = mocker.spy(model, "_get_playlists")
        yield mock_playlists

        mock_playlists.assert_any_call(model.source)
        mock_playlists.assert_any_call(model.target)

        if model.reference is not None:
            mock_playlists.assert_any_call(model.reference)

    @pytest.fixture
    def mock_remove(
            self,
            model: SyncLocalPlaylists,
            source_playlists: list[LocalPlaylist],
            target_playlists: list[LocalPlaylist],
            reference_playlists: list[LocalPlaylist],
            mocker: MockerFixture,
    ) -> Generator[Mock]:
        mock_remove = mocker.spy(model, "_remove_playlists")
        yield mock_remove
        mock_remove.assert_called_once_with(source_playlists, target_playlists, reference_playlists)

    @pytest.fixture
    def mock_merge(
            self,
            model: SyncLocalPlaylists,
            source_playlists: list[LocalPlaylist],
            target_playlists: list[LocalPlaylist],
            reference_playlists: list[LocalPlaylist],
            mocker: MockerFixture,
    ) -> Generator[Mock]:
        mock_merge = mocker.spy(type(model.source), "merge_playlists")
        yield mock_merge

        mock_merge.assert_any_call(model.source, target_playlists, reference=reference_playlists)
        mock_merge.assert_any_call(model.target, source_playlists, reference=reference_playlists)

    @pytest.fixture
    def mock_save_source(self, model: SyncLocalPlaylists, mocker: MockerFixture) -> Generator[Mock]:
        mock_save = mocker.spy(model.source.save_playlists, "func")
        with patch.object(model.source, "_run_tasks_async", return_value={}) as mock_run:
            yield mock_run

        mock_save.assert_called_once_with(dry_run=model.state.dry_run)

    @pytest.fixture
    def mock_save_target(self, model: SyncLocalPlaylists, mocker: MockerFixture) -> Generator[Mock]:
        mock_save = mocker.spy(model.target.save_playlists, "func")
        with patch.object(model.target, "_run_tasks_async", return_value={}) as mock_run:
            yield mock_run

        mock_save.assert_called_once_with(dry_run=model.state.dry_run)

    @pytest.fixture
    def mock_save_reference(self, model: SyncLocalPlaylists, mocker: MockerFixture) -> Generator[Mock]:
        mock_save = mocker.spy(model.reference.save_playlists, "func")
        with patch.object(model.reference, "_run_tasks_async", return_value={}) as mock_run:
            yield mock_run

        if model.reference is not None:
            mock_save.assert_called_once_with(dry_run=model.state.dry_run)
        else:
            mock_save.assert_not_called()

    async def test_run(
            self,
            model: SyncLocalPlaylists,
            mock_playlists: Mock,
            mock_remove: Mock,
            mock_merge: Mock,
            mock_save_source: Mock,
            mock_save_target: Mock,
            mock_save_reference: Mock,
    ):
        await model.run()
        # assertions happen in mock teardowns

    async def test_run_no_reference(
            self,
            model: SyncLocalPlaylists,
            reference_playlists: list[LocalPlaylist],
            mock_playlists: Mock,
            mock_remove: Mock,
            mock_merge: Mock,
            mock_save_source: Mock,
            mock_save_target: Mock,
            mock_save_reference: Mock,
    ):
        model.reference_name = None
        reference_playlists.clear()  # clear in place to ensure mock teardown assertions work as expected
        assert model.reference is None

        await model.run()
        # assertions happen in mock teardowns


class TestSyncLocalAndRemotePlaylists(OperationTester):
    @pytest.fixture
    def model(
            self, state: GlobalState, local_library_name: str, remote_library_name: str, faker: Faker
    ) -> SyncLocalAndRemotePlaylists:

        return SyncLocalAndRemotePlaylists(
            state=state,
            source_name=local_library_name,
            target_name=remote_library_name,
            type=faker.random_element(get_args(SYNC_TYPE)),
        )

    @pytest.fixture
    def mock_playlists(
            self, model: SyncLocalAndRemotePlaylists, playlists: list[Playlist], mocker: MockerFixture
    ) -> Generator[Mock]:
        mock_playlists = mocker.spy(model, "_get_playlists")
        yield mock_playlists
        mock_playlists.assert_called_once_with(model.source)

    async def test_run(
            self,
            model: SyncLocalAndRemotePlaylists,
            playlists: list[Playlist],
            mock_playlists: Mock,
            mocker: MockerFixture
    ):
        model.source.playlists.extend(playlists)

        mock_merge = mocker.spy(type(model.target), "merge_playlists")
        mock_sync = mocker.spy(model.target.sync_playlists, "func")  # save_state.func

        await model.run()

        mock_merge.assert_called_once_with(model.target, playlists)
        mock_sync.assert_called_once_with(kind=model.type, dry_run=model.state.dry_run)
