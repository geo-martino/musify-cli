from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import pytest
from faker import Faker
from mytunes.processors.time import TimeMapper

from mytunes_cli.operations.backup.utils import Clean
from mytunes_cli.state import GlobalState
from operations.testers import OperationTester


class TestClean(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState, library_name: str) -> Clean:
        state = state.model_copy(update=dict(dry_run=False))
        return Clean(state=state, library_name=library_name)

    @pytest.fixture
    def backup_key(self, model: Clean, faker: Faker) -> str:
        return faker.word()

    @pytest.fixture(autouse=True)
    def backup_paths(self, model: Clean, state: GlobalState, faker: Faker) -> list[Path]:
        """Generate a set of backup files and return their paths"""
        now = datetime.now()

        paths = []
        for i in range(1, 50, 2):
            timestamp = state.parse_timestamp(now - timedelta(hours=i))
            path = model.backup_dir.joinpath(f"{timestamp}.{faker.file_extension(category="text")}")
            path.parent.mkdir(parents=True, exist_ok=True)

            paths.append(path)

            with path.open("w") as f:
                for _ in range(600):
                    f.write(faker.pystr())

        return paths

    @pytest.fixture(autouse=True)
    def backup_paths_with_key(self, model: Clean, backup_key: str, faker: Faker) -> list[Path]:
        """Generate a set of backup files with backup keys in the filenames and return their paths"""
        now = datetime.now().replace(microsecond=0)

        paths = []
        for i in range(1, 50, 2):
            timestamp = model.state.parse_timestamp(now - timedelta(hours=i))
            path = model.backup_dir.joinpath(f"{timestamp} ({backup_key}).{faker.file_extension(category="text")}")
            paths.append(path)

            with open(path, "w") as f:
                for _ in range(600):
                    f.write(faker.pystr())

        return paths

    @staticmethod
    def get_expected_oldest(model: Clean, paths: list[Path], faker: Faker) -> Path:
        oldest_expected = faker.random_element(paths)
        oldest_expected_dt = model.state.parse_datetime(oldest_expected.stem.split()[0])
        model.delta = TimeMapper(amount=int((model.state.dt - oldest_expected_dt).total_seconds()) + 1, unit="seconds")

        return oldest_expected

    @staticmethod
    def get_expected_count(model: Clean, paths: list[Path], faker: Faker) -> list[Path]:
        expected = list(reversed(sorted(paths)))[:faker.random_int(1, len(paths) // 2)]
        model.count = len(expected)

        return expected

    @staticmethod
    def get_existing_paths(model: Clean) -> list[Path]:
        return [path for path in sorted(model.backup_dir.rglob("*")) if path.exists()]

    @classmethod
    def assert_expected_paths(cls, model: Clean, expected: Iterable[Path]) -> None:
        assert cls.get_existing_paths(model) == sorted(expected)

    @classmethod
    def assert_oldest_path(cls, model: Clean, oldest: Path, paths: list[Path], others: list[Path]) -> None:
        paths = sorted(paths)
        expected = paths[paths.index(oldest):] + others
        cls.assert_expected_paths(model, expected)

    async def test_remove_old_backups(
            self, model: Clean, backup_paths: list[Path], backup_paths_with_key: list[Path], faker: Faker
    ):
        expected = self.get_expected_oldest(model, paths=backup_paths, faker=faker)

        await model.run()
        self.assert_oldest_path(model, oldest=expected, paths=backup_paths, others=backup_paths_with_key)

    async def test_remove_old_backups_with_key(
            self,
            model: Clean,
            backup_paths: list[Path],
            backup_paths_with_key: list[Path],
            backup_key: str,
            faker: Faker,
    ):
        model.key = backup_key
        expected = self.get_expected_oldest(model, paths=backup_paths_with_key, faker=faker)

        await model.run()
        self.assert_oldest_path(model, oldest=expected, paths=backup_paths_with_key, others=backup_paths)

    async def test_remove_too_many_backups(
            self, model: Clean, backup_paths: list[Path], backup_paths_with_key: list[Path], faker: Faker
    ):
        expected = self.get_expected_count(model, paths=backup_paths, faker=faker)

        await model.run()
        self.assert_expected_paths(model, expected + backup_paths_with_key)

    async def test_remove_too_many_backups_with_key(
            self,
            model: Clean,
            backup_paths: list[Path],
            backup_paths_with_key: list[Path],
            backup_key: str,
            faker: Faker,
    ):
        model.key = backup_key
        expected = self.get_expected_count(model, paths=backup_paths_with_key, faker=faker)

        await model.run()
        self.assert_expected_paths(model, expected + backup_paths)

    async def test_remove_combined(
            self, model: Clean, backup_paths: list[Path], backup_paths_with_key: list[Path], faker: Faker
    ):
        paths = sorted(self.get_expected_count(model, paths=backup_paths, faker=faker))
        expected = self.get_expected_oldest(model, paths=paths, faker=faker)

        await model.run()
        self.assert_oldest_path(model, oldest=expected, paths=paths, others=backup_paths_with_key)

    async def test_remove_combined_with_key(
            self,
            model: Clean,
            backup_paths: list[Path],
            backup_paths_with_key: list[Path],
            backup_key: str,
            faker: Faker,
    ):
        model.key = backup_key
        paths = sorted(self.get_expected_count(model, paths=backup_paths_with_key, faker=faker))
        expected = self.get_expected_oldest(model, paths=paths, faker=faker)

        await model.run()
        self.assert_oldest_path(model, oldest=expected, paths=paths, others=backup_paths)

    async def test_remove_dry_run(
            self, model: Clean, backup_paths: list[Path], backup_paths_with_key: list[Path], faker: Faker
    ):
        model.state = model.state.model_copy(update=dict(dry_run=True))

        model.count = faker.random_int(1, len(backup_paths))
        model.delta = TimeMapper(amount=30, unit="seconds")

        await model.run()
        self.assert_expected_paths(model, backup_paths + backup_paths_with_key)
