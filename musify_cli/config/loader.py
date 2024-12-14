"""
Handles loading of config from a config file (e.g. YAML or JSON).
"""
import json
from collections.abc import Mapping
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Any

import yaml
from musify.utils import to_collection, merge_maps

from musify_cli.exception import ParserError


class MultiFileLoader(yaml.SafeLoader):
    """YAML loader which includes additional YAML files from paths found within a given parent YAML file."""

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

        self._include_key = "include"

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = True):
        """Construct mapping object and apply line and column numbers"""
        mapping = super().construct_mapping(node, deep=deep)
        if self._include_key not in mapping:
            return mapping

        paths = list(map(Path, to_collection(mapping.pop(self._include_key))))
        for path in paths:
            if not path.is_absolute() and isinstance(self._parent_path, Path):
                path = self._parent_path.joinpath(path)
            if not path.is_file():
                continue

            include = self.load(path)
            if isinstance(include, Mapping):
                merge_maps(mapping, include, extend=False, overwrite=False)
            else:
                raise ParserError(f"Loaded file at {path=} is not a mapping. ", value=include)

        return mapping
