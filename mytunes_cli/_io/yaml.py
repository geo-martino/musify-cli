"""
Handles loading of config from a config file (e.g. YAML or JSON).
"""
import json
from collections.abc import Hashable
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import YamlConfigSettingsSource

from mytunes_cli._io._utils import get_path
from mytunes_cli._io.exception import ParserError


class MultiFileYamlConfigSettingsSource(YamlConfigSettingsSource):
    def _read_file(self, file_path: Path) -> dict[str, Any]:
        with file_path.open(encoding=self.yaml_file_encoding) as file:
            return yaml.load(file, MultiFileLoader) or {}


class MultiFileLoader(yaml.SafeLoader):
    """YAML loader which includes additional YAML files from paths found within a given parent YAML file."""
    _include_key = "_include"

    @classmethod
    def load(cls, path: str | Path) -> Any:
        """
        Load a file of any recognised file type by this loader from the given ``path``.

        :param path: The path of the file to load.
        :raise ParserError: If the file type is not recognised.
        """
        match (path := Path(path)).suffix.casefold():
            case ".json":
                return cls._load_json(path)
            case suffix if suffix in (".yml", ".yaml"):
                return cls._load_yaml(path)
            case _:
                raise ParserError("Unrecognised file type", value=path)

    @staticmethod
    @contextmanager
    def _load_stream(path: str | Path) -> TextIOWrapper:
        with Path(path).open("r", encoding="utf-8") as stream:
            yield stream

    @classmethod
    def _load_yaml(cls, path: str | Path) -> Any:
        with cls._load_stream(path) as stream:
            return yaml.load(stream, cls)

    @classmethod
    def _load_json(cls, path: str | Path) -> Any:
        with cls._load_stream(path) as stream:
            return json.load(stream)

    def __init__(self, stream: Any):
        super().__init__(stream)
        try:
            self._parent_path = Path(stream.name).parent
        except AttributeError:
            self._parent_path = Path.cwd()

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = True) -> dict[Hashable, Any]:
        """Construct mapping object and apply line and column numbers"""
        mapping = super().construct_mapping(node, deep=deep)
        if self._include_key not in mapping:
            return mapping

        value = get_path(mapping.pop(self._include_key))
        if not isinstance(value, Path):
            mapping[self._include_key] = value  # add value back, it isn't a path
            return mapping

        path = value
        if not path.is_absolute() and isinstance(self._parent_path, Path):
            path = self._parent_path.joinpath(path)

        if not path.is_file():
            mapping[self._include_key] = value  # add value back, it isn't a file
            return mapping

        include = self.load(path)
        if isinstance(include, dict):
            mapping = self._deep_update(mapping, include)
        else:
            raise ParserError(f"Loaded file at {path=} is not a mapping.", value=include)

        return mapping

    # This is just copied from Pydantic v1 to avoid deprecation warnings
    @classmethod
    def _deep_update[T: Hashable](cls, mapping: dict[T, Any], *updating_mappings: dict[T, Any]) -> dict[T, Any]:
        updated_mapping = mapping.copy()
        for updating_mapping in updating_mappings:
            for k, v in updating_mapping.items():
                if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
                    updated_mapping[k] = cls._deep_update(updated_mapping[k], v)
                else:
                    updated_mapping[k] = v

        return updated_mapping
