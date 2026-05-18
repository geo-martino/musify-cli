from pathlib import Path
from typing import Any

import pytest
from faker import Faker
from mytunes.core.library import Library, RemoteMutableLibrary
from mytunes.exception import MyTunesKeyError, MyTunesTypeError
from mytunes.local.library import LocalLibrary

from mytunes_cli.state import GlobalState
from mytunes_cli.state._decorators import load_state, save_state
from mytunes_cli.state.paths import GlobalPaths


# noinspection PyAbstractClass
class TestGlobalSettings:
    @pytest.fixture
    def model(self, libraries: dict[str, Library], tmp_path: Path) -> GlobalState:
        paths = GlobalPaths(application=tmp_path)
        return GlobalState(paths=paths, libraries=libraries)

    def test_dt_remains_constant(self, model: GlobalState):
        assert model.dt is model.dt is model.dt

    def test_get_library(self, model: GlobalState, faker: Faker):
        name, library = faker.random_element(model.libraries.items())
        assert model.get_library(name) is library

    def test_fails_on_unknown_library(self, model: GlobalState, faker: Faker):
        name = faker.sentence()
        assert name not in model.libraries

        with pytest.raises(MyTunesKeyError, match="not found"):
            assert model.get_library(name)

        with pytest.raises(MyTunesKeyError, match="not found"):
            assert model.get_local_library(name)

        with pytest.raises(MyTunesKeyError, match="not found"):
            assert model.get_remote_library(name)

        with pytest.raises(MyTunesKeyError, match="not found"):
            assert model.get_mutable_remote_library(name)

    def test_get_local_library(
            self,
            model: GlobalState,
            local_libraries: dict[str, LocalLibrary],
            remote_libraries: dict[str, RemoteMutableLibrary],
            faker: Faker,
    ):
        name, library = faker.random_element(local_libraries.items())
        assert name not in remote_libraries

        assert model.get_local_library(name) is library

    def test_fails_on_invalid_local_library(
            self,
            model: GlobalState,
            local_libraries: dict[str, LocalLibrary],
            remote_libraries: dict[str, RemoteMutableLibrary],
            faker: Faker,
    ):
        name, library = faker.random_element(remote_libraries.items())
        assert name not in local_libraries

        with pytest.raises(MyTunesTypeError, match="not a local library"):
            assert model.get_local_library(name)

    def test_get_remote_library(
            self,
            model: GlobalState,
            local_libraries: dict[str, LocalLibrary],
            remote_libraries: dict[str, RemoteMutableLibrary],
            faker: Faker,
    ):
        name, library = faker.random_element(remote_libraries.items())
        assert name not in local_libraries

        assert model.get_remote_library(name) is library

    def test_fails_on_invalid_remote_library(
            self,
            model: GlobalState,
            local_libraries: dict[str, LocalLibrary],
            remote_libraries: dict[str, RemoteMutableLibrary],
            faker: Faker,
    ):
        name, library = faker.random_element(local_libraries.items())
        assert name not in remote_libraries

        with pytest.raises(MyTunesTypeError, match="not a remote library"):
            assert model.get_remote_library(name)

    def test_get_mutable_remote_library(
            self,
            model: GlobalState,
            local_libraries: dict[str, LocalLibrary],
            remote_libraries: dict[str, RemoteMutableLibrary],
            faker: Faker,
    ):
        name, library = faker.random_element(remote_libraries.items())
        assert name not in local_libraries

        assert model.get_mutable_remote_library(name) is library

    def test_fails_on_invalid_mutable_remote_library(
            self,
            model: GlobalState,
            local_libraries: dict[str, LocalLibrary],
            remote_libraries: dict[str, RemoteMutableLibrary],
            faker: Faker,
    ):
        name, library = faker.random_element(local_libraries.items())
        assert name not in remote_libraries

        with pytest.raises(MyTunesTypeError, match="not a mutable remote library"):
            assert model.get_mutable_remote_library(name)

    @staticmethod
    def assert_load_state_management(name: str, method: Any, prefix: str) -> None:
        if not callable(method):
            return
        if name != prefix and not name.startswith(f"{prefix}_"):
            return

        assert isinstance(method, load_state)

    @staticmethod
    def assert_save_state_management(name: str, method: Any, prefix: str) -> None:
        if not callable(method):
            return

        if name == prefix or name.startswith(f"{prefix}_"):
            assert isinstance(method, save_state)

    def test_set_state_management_for_immutable_libraries(self, model: GlobalState) -> None:
        for library in model.libraries.values():
            for name, method in vars(library).items():
                self.assert_load_state_management(name, method, prefix="load")

    def test_set_state_management_for_mutable_local_libraries(self, model: GlobalState) -> None:
        for library in model.libraries.values():
            if not isinstance(library, LocalLibrary):
                continue

            for name, method in vars(library).items():
                self.assert_save_state_management(name, method, prefix="save")

    def test_set_state_management_for_mutable_remote_libraries(self, model: GlobalState) -> None:
        for library in model.libraries.values():
            if not isinstance(library, RemoteMutableLibrary):
                continue

            for name, method in vars(library).items():
                self.assert_save_state_management(name, method, prefix="sync")
                self.assert_save_state_management(name, method, prefix="save")

    def test_parse_state(self):
        pass  # TODO

    def test_parse_logging_config(self):
        pass  # TODO
