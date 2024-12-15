import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from musify_cli.config.loader import MultiFileLoader
from musify_cli.exception import ParserError


class TestMultiFileLoader:
    @pytest.fixture
    def data(self) -> dict[str, Any]:
        return {
            "key1": "val1",
            "key2": 2,
            "key3": {
                "sub_key1": "val1",
                "sub_key2": [1, 2, 3],
            }
        }

    @staticmethod
    def assert_load(data: dict[str, Any], path: Path) -> None:
        """Assert the file at the given ``path`` returns the expected ``data``"""
        assert MultiFileLoader.load(path) == data
        assert MultiFileLoader.load(str(path)) == data

    def test_load_json(self, data: dict[str, Any], tmp_path: Path):
        path = tmp_path.joinpath("test.json")
        with path.open("w") as file:
            json.dump(data, file)

        self.assert_load(data, path)

    def test_load_yml(self, data: dict[str, Any], tmp_path: Path):
        path = tmp_path.joinpath("test.YML")
        with path.open("w") as file:
            yaml.dump(data, file)

        self.assert_load(data, path)

    def test_load_yaml(self, data: dict[str, Any], tmp_path: Path):
        path = tmp_path.joinpath("test.yaml")
        with path.open("w") as file:
            yaml.dump(data, file)

        self.assert_load(data, path)

    def test_includes_mapping(self, data: dict[str, Any], tmp_path: Path):
        path_parent = tmp_path.joinpath("test.yaml")
        path_child1 = tmp_path.joinpath("child1.yml")
        path_child2 = tmp_path.joinpath("child2.json")

        with path_child1.open("w") as file:
            yaml.dump(data, file)
        with path_child2.open("w") as file:
            json.dump(data, file)

        data_parent = deepcopy(data)
        data_parent["child1"] = {"include": path_child1.name}
        data_parent["child2"] = {"include": [str(path_child1), str(path_child2)], "other_key": "other_value"}
        with path_parent.open("w") as file:
            yaml.dump(data_parent, file)

        expected = deepcopy(data)
        expected["child1"] = data | {k: v for k, v in data_parent["child1"].items() if k != "include"}
        expected["child2"] = data | {k: v for k, v in data_parent["child2"].items() if k != "include"}

        self.assert_load(expected, path_parent)

    def test_fails_on_list_include(self, data: dict[str, Any], tmp_path: Path):
        path_parent = tmp_path.joinpath("test.yaml")
        path_child = tmp_path.joinpath("child.yml")

        with path_child.open("w") as file:
            yaml.dump([1, 2, 3, 4], file)

        data_parent = deepcopy(data)
        data_parent["child"] = {"include": str(path_child)}
        with path_parent.open("w") as file:
            yaml.dump(data_parent, file)

        with pytest.raises(ParserError):
            MultiFileLoader.load(path_parent)

    def test_fails_on_str_include(self, data: dict[str, Any], tmp_path: Path):
        path_parent = tmp_path.joinpath("test.yaml")
        path_child = tmp_path.joinpath("child2.yaml")
        with path_child.open("w") as file:
            json.dump("not a mapping", file)

        data_parent = deepcopy(data)
        data_parent["child1"] = {"include": str(path_child)}
        with path_parent.open("w") as file:
            yaml.dump(data_parent, file)

        with pytest.raises(ParserError):
            MultiFileLoader.load(path_parent)
