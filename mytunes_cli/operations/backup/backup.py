from collections.abc import Mapping
from pathlib import Path
from typing import Any

import aiofiles
import yaml

from mytunes_cli.operations.backup._base import _BaseOperation


class Backup(_BaseOperation):
    async def load(self) -> None:
        await self.library.load()

    async def run(self) -> None:
        dump = self.library.dump()
        await self._save_yaml(dump)

    async def _save_yaml(self, data: Mapping[str, Any]) -> None:
        path = Path(str(self.backup_path) + ".yaml")
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, "w", encoding="utf-8") as file:
            await file.write(yaml.dump(data, indent=2))

        self._logger.info(f"Saved YAML file: [green]{path}[/]", header=2)

    def _log_start(self) -> None:
        message = f"Generating backup for {self.library.source} library: {self.library_name}"
        self._logger.info(message, header=1, new_line_start=True)
