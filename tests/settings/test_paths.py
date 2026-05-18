from pathlib import Path

import pytest
from faker import Faker
from pydantic_core import ValidationError

from mytunes_cli.state.paths import GlobalPaths


class TestApplicationPaths:
    @pytest.fixture
    def model(self, tmp_path: Path, faker: Faker) -> GlobalPaths:
        return GlobalPaths(
            application=tmp_path,
            config=tmp_path.joinpath(*faker.words()),
            logs=tmp_path.joinpath(*faker.words()),
        )

    def test_from_path(self, model: GlobalPaths, faker: Faker):
        path = Path(*faker.words())
        assert GlobalPaths.model_validate(path).application == Path(path)

    def test_fails_on_file_paths(self, model: GlobalPaths, faker: Faker):
        with pytest.raises(ValidationError, match="path_not_directory"):
            model.config = Path(faker.file_path())

    def test_set_absolute_paths(self, model: GlobalPaths):
        assert all(not path.is_absolute() for path in vars(GlobalPaths).values() if isinstance(path, Path))

        with model:
            assert all(path.is_absolute() for path in vars(GlobalPaths).values() if isinstance(path, Path))

    def test_create_directories(self, model: GlobalPaths):
        assert all(not path.exists() for path in vars(GlobalPaths).values() if isinstance(path, Path))

        with model:
            assert all(path.is_dir() for path in vars(GlobalPaths).values() if isinstance(path, Path))

    def test_remove_empty_directories(self, model: GlobalPaths):
        assert all(not path.exists() for path in vars(GlobalPaths).values() if isinstance(path, Path))

        with model:
            assert all(path.is_dir() for path in vars(GlobalPaths).values() if isinstance(path, Path))
            assert not any(list(path.rglob("*")) for path in vars(GlobalPaths).values() if isinstance(path, Path))

        assert all(not path.exists() for path in vars(GlobalPaths).values() if isinstance(path, Path))

    def test_remove_skips_non_empty_directories(self, model: GlobalPaths, faker: Faker):
        assert all(not path.exists() for path in vars(GlobalPaths).values() if isinstance(path, Path))
        paths = []

        with model:
            assert all(path.is_dir() for path in vars(GlobalPaths).values() if isinstance(path, Path))
            for path in vars(GlobalPaths).values():
                if not isinstance(path, Path):
                    continue

                for _ in range(faker.random_int(min=1, max=5)):
                    depth = faker.random_int(1, 3)
                    path.joinpath(faker.file_path(depth=depth, absolute=False)).touch(exist_ok=True)
                    paths.append(path)

        assert all(path.exists() for path in vars(GlobalPaths).values() if isinstance(path, Path))
        assert all(path.exists() for path in paths)
