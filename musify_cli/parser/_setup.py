"""
Operations for setting up the jsonargparse package for this program.
"""
from copy import deepcopy
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable
import yaml

from jsonargparse import Namespace, set_dumper
# noinspection PyProtectedMember
from jsonargparse._loaders_dumpers import dump_yaml_kwargs
from jsonargparse.typing import register_type

from musify.core.printer import PrettyPrinter
from musify.processors.filter import FilterComparers


def _make_yaml_safe(config: dict[str, Any]) -> None:
    for key, value in config.items():
        if isinstance(value, FilterComparers):
            comparers = {comparer.condition: comparer.expected for comparer in value.comparers}
            config[key] = {"match_all": value.match_all} | comparers
        elif isinstance(value, PrettyPrinter):
            value = value.as_dict()
            _make_yaml_safe(value)
            config[key] = value
        elif isinstance(value, Enum):
            config[key] = value.name.lower()
        elif isinstance(value, Iterable) and all(isinstance(v, Enum) for v in value):
            config[key] = [v.name.lower() for v in value]
        elif isinstance(value, dict):
            _make_yaml_safe(value)


def yaml_dump(data: dict[str, Any] | Namespace) -> str:
    data = data.as_dict() if isinstance(data, Namespace) else deepcopy(data)
    _make_yaml_safe(data)
    return yaml.safe_dump(data, **dump_yaml_kwargs)


def setup() -> None:
    """Setup app-specific options for jsonargparse"""
    register_type(
        date,
        serializer=lambda x: x.strftime("%Y-%m-%d") if isinstance(x, datetime) else x,
        deserializer=lambda x: datetime.strptime(x, "%Y-%m-%d") if isinstance(x, str) else x,
    )

    set_dumper("yaml", yaml_dump)
