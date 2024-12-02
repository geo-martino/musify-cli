import json
import logging
import logging.config
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from functools import cached_property
from pathlib import Path
from typing import Any

from aiorequestful.types import UnitCollection
from musify.libraries.core.object import Library
from musify.logger import MusifyLogger
from musify.types import MusifyEnum
from musify.utils import get_user_input

from musify_cli.config.library import LibraryConfig


class LibraryManager[L: Library, C: LibraryConfig](ABC):
    """Generic base class for instantiating and managing a library and related objects from a given ``config``."""

    def __init__(self, config: C, dry_run: bool = True):
        # noinspection PyTypeChecker
        self.logger: MusifyLogger = logging.getLogger(__name__)

        self.initialised = False

        self.config: C = config
        self.dry_run = dry_run

    @property
    def name(self) -> str:
        """The user-defined name of the library"""
        return self.config.name

    @property
    def source(self) -> str:
        """The name of the source currently being used for this library"""
        return self.config.source

    @cached_property
    def library(self) -> L:
        """The initialised library"""
        self.initialised = True
        return self.config.create()

    ###########################################################################
    ## Backup/Restore - Utilities
    ###########################################################################
    def _save_json(self, path: str | Path, data: Mapping[str, Any]) -> None:
        """Save a JSON file to a given ``path``"""
        path = Path(path).with_suffix(".json")

        with open(path, "w") as file:
            json.dump(data, file, indent=2)

        self.logger.info(f"\33[1;95m  >\33[1;97m Saved JSON file: \33[1;92m{path}\33[0m")

    def _load_json(self, path: Path) -> dict[str, Any]:
        """Load a stored JSON file from a given ``path``"""
        path = Path(path).with_suffix(".json")

        with open(path, "r") as file:
            data = json.load(file)

        self.logger.info(f"\33[1;95m  >\33[1;97m Loaded JSON file: \33[1;92m{path}\33[0m")
        return data

    def _get_library_backup_name(self, key: str | None = None) -> str:
        """The identifier to use in filenames of the :py:class:`Library`"""
        name = f"{self.library.__class__.__name__} - {self.library.name}"
        if key:
            name = f"[{key.upper()}] - {name}"
        return name

    ###########################################################################
    ## Backup
    ###########################################################################
    async def backup(self, backup_folder: Path, key: str | None = None) -> None:
        """Backup data for all tracks and playlists in all libraries"""
        self.logger.debug(f"Backup {self.source}: START")

        if not key:
            key = get_user_input("Enter a key for this backup. Hit return to backup without a key")
            self.logger.print_line()

        await self._load_library_for_backup()

        backup_path = Path(backup_folder, self._get_library_backup_name(key))
        self._save_json(backup_path, self.library.json())

        self.logger.debug(f"Backup {self.source}: DONE")

    @abstractmethod
    async def _load_library_for_backup(self) -> None:
        raise NotImplementedError

    ###########################################################################
    ## Restore
    ###########################################################################
    async def restore(self, backup_folder: Path) -> None:
        """Restore library data from a backup, getting user input for the settings"""
        available_groups = self._get_available_backup_groups(backup_folder)
        if len(available_groups) == 0:
            self.logger.info("\33[93mNo backups found, skipping.\33[0m")
            return

        restore_dir = self._get_restore_dir_from_user(backup_folder)
        restore_key = self._get_restore_key_from_user(restore_dir)
        restore_path = restore_dir.joinpath(restore_key)

        self.logger.debug(f"Restore {self.source}: START")
        await self._restore_library(restore_path)

        self.logger.info(f"\33[92mSuccessfully restored {self.source} library: {self.name}\33[0m")
        self.logger.debug(f"Restore {self.source}: DONE")

    @abstractmethod
    async def _restore_library(self, path: Path) -> None:
        """Restore library data from a backup ``path``, getting user input for the settings as needed"""

    def _get_available_backup_groups(self, backup_folder: Path) -> list[str]:
        backup_name = self._get_library_backup_name()

        available_backups: list[str] = []  # names of the folders which contain usable backups
        for parent, _, filenames in backup_folder.walk():
            if parent == backup_folder:  # skip current run's data
                continue
            group = parent.relative_to(backup_folder).name  # backup group is the folder name

            for file in map(Path, filenames):
                if group in available_backups:
                    break
                if backup_name in file.stem:
                    available_backups.append(group)
                    break

        return available_backups

    def _get_restore_dir_from_user(self, backup_folder: Path) -> Path:
        available_groups = self._get_available_backup_groups(backup_folder)

        self.logger.info(
            "\33[97mAvailable backups: \n\t\33[97m- \33[94m{}\33[0m"
            .format("\33[0m\n\t\33[97m-\33[0m \33[94m".join(available_groups))
        )
        available_groups = {group.casefold() for group in available_groups}

        while True:  # get valid user input
            group = get_user_input("Select the backup to use")
            if group.casefold() in available_groups:  # input is valid
                break
            print(f"\33[91mBackup '{group}' not recognised, try again\33[0m")

        return backup_folder.joinpath(group)

    def _get_restore_key_from_user(self, path: Path) -> str:
        available_keys = {re.sub(r"^\[(\w+)].*", "\\1", file) for file in os.listdir(path)}

        self.logger.info(
            "\33[97mAvailable backup keys: \n\t\33[97m- \33[94m{}\33[0m"
            .format("\33[0m\n\t\33[97m-\33[0m \33[94m".join(available_keys))
        )
        available_keys = {key.casefold() for key in available_keys}

        while True:  # get valid user input
            key = get_user_input("Select the backup type to use")
            if key.casefold() in available_keys:  # input is valid
                break
            print(f"\33[91mBackup '{key}' not recognised, try again\33[0m")

        return self._get_library_backup_name(key)

    @abstractmethod
    async def load(self, types: UnitCollection[MusifyEnum] = (), force: bool = False) -> None:
        """
        Load items/collections in the instantiated library based on the given ``types``.

        :param types: The types of items/collections to load.
        :param force: Whether to reload the given ``types`` even if they have already been loaded before.
            When False, only load the ``types`` that have not been loaded.
        """
        raise NotImplementedError
