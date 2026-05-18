import os
import re
from datetime import datetime
from pathlib import Path
from typing import Generator

from mytunes.processors.time import TimeMapper
from pydantic import Field

from mytunes_cli.operations.backup._base import _BaseOperation


class Clean(_BaseOperation):
    delta: TimeMapper | None = Field(
        description="The maximum age of backups to keep.",
        default=None,
    )
    count: int | None = Field(
        description="The maximum number of backups to keep.",
        default=None,
    )

    async def run(self):
        paths = sorted(self._get_paths(self.backup_timestamps))
        remaining = len(paths)

        if not remaining:
            self._logger.warning("[yellow]No backups found, skipping.[/]")
            return

        removed = []

        for path in paths:
            if self._too_many(remaining) or self._too_old(path):
                if not self.state.dry_run:
                    os.remove(path)

                removed.append(path.name)
                remaining -= 1

        self._log_removed(removed)

    def _get_paths(self, timestamps: list[datetime]) -> Generator[Path]:
        for path in self.backup_dir.rglob("*"):
            timestamp = self._remove_key(path).stem
            if self.key and timestamp == path.stem:  # skip processing non-keyed backups when key is set
                continue

            dt = self.state.parse_datetime(timestamp)
            if dt in timestamps:
                yield path

    def _remove_key(self, path: Path) -> Path:
        if not self.key:
            return path
        return path.with_stem(re.sub(rf" \({self.key}\)", "", path.stem))

    def _too_many(self, available: int) -> bool:
        return available > self.count if self.count is not None else False

    def _too_old(self, path: Path) -> bool:
        timestamp = self._remove_key(path).stem
        dt = self.state.parse_datetime(timestamp)
        return self.delta is not None and dt < self.delta.apply(self.state.dt) if dt else False

    def _log_removed(self, paths: list[Path]) -> None:
        log_prefix = "Would have removed" if self.state.dry_run else "Removed"
        message = f"{log_prefix} {len(paths)} library backups for {self.library_name!r}"
        self._logger.info(f"[green]{message}[/]")
