from datetime import datetime, timedelta
from pathlib import Path

import pytest
from faker import Faker

from mytunes_cli.log.handlers import FilenameTimedRotatingFileHandler
from mytunes_cli.state import GlobalState


class TestFilenameTimedRotatingFileHandler:
    @pytest.fixture
    def current_log_path(self, state: GlobalState, tmp_path: Path) -> Path:
        return state.paths.logs.joinpath(state.timestamp + ".log")

    @pytest.fixture(autouse=True)
    def other_log_paths(self, state: GlobalState, current_log_path: Path, faker: Faker) -> list[Path]:
        """Generate a set of log files and return their paths"""
        dt_now = datetime.now()

        paths = []
        for i in range(1, 50, 2):
            timestamp = state.parse_timestamp(dt_now - timedelta(hours=i))
            path = current_log_path.parent.joinpath(timestamp + ".log")
            path.parent.mkdir(parents=True, exist_ok=True)

            paths.append(path)

            with path.open("w") as f:
                for _ in range(600):
                    f.write(faker.pystr())

        return paths

    def test_removes_logs_when_too_old(self, state: GlobalState, current_log_path: Path):
        FilenameTimedRotatingFileHandler(path=current_log_path.parent, dt=state.timestamp, when="h", interval=10)

        for path in current_log_path.parent.glob("*"):
            dt = state.parse_datetime(path.stem)
            assert dt >= state.dt - timedelta(hours=10)

    def test_removes_logs_when_too_many(self, state: GlobalState, current_log_path: Path):
        FilenameTimedRotatingFileHandler(path=current_log_path.parent, dt=state.timestamp, count=10)
        assert len(list(current_log_path.parent.glob("*"))) == 9  # -1 for current file/folder

    def test_removes_logs_combined(self, state: GlobalState, current_log_path: Path):
        FilenameTimedRotatingFileHandler(
            path=current_log_path.parent, dt=state.timestamp, when="h", interval=10, count=3
        )

        for path in current_log_path.parent.glob("*"):
            dt = state.parse_datetime(path.stem)
            assert dt >= state.dt - timedelta(hours=10)

        assert len(list(current_log_path.parent.glob("*"))) <= 3
