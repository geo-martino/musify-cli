"""
Operations for setting up the jsonargparse package for this program.
"""
import re
from collections.abc import Iterable
from copy import deepcopy
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import PurePath
from typing import Any

import jsonargparse
import yaml
from dateutil.relativedelta import relativedelta

from jsonargparse import Namespace, set_dumper
# noinspection PyProtectedMember
from jsonargparse._loaders_dumpers import dump_yaml_kwargs
from jsonargparse.typing import register_type

from musify.core.printer import PrettyPrinter
from musify.processors.base import dynamicprocessormethod
from musify.processors.filter import FilterComparers
from musify.processors.time import TimeMapper

from musify_cli.parser.types import SensitiveString


###########################################################################
## Dumpers
###########################################################################
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
        elif isinstance(value, PurePath | jsonargparse.Path):
            config[key] = str(value)
        elif isinstance(value, Iterable) and all(isinstance(v, PurePath | jsonargparse.Path) for v in value):
            config[key] = [str(v) for v in value]
        elif isinstance(value, SensitiveString):
            config[key] = "<REDACTED>"
        elif isinstance(value, dict):
            _make_yaml_safe(value)


def yaml_dump(data: dict[str, Any] | Namespace) -> str:
    data = data.as_dict() if isinstance(data, Namespace) else deepcopy(data)
    _make_yaml_safe(data)
    return yaml.safe_dump(data, **dump_yaml_kwargs)


###########################################################################
## Type serialization registration
###########################################################################
TIME_MAPPER_HELP_CHOICES = {
    key[0] if not value.alternative_names else value.alternative_names[0]: key
    for key, value in vars(TimeMapper).items() if isinstance(value, dynamicprocessormethod)
}
TIME_MAPPER_HELP_TEXT = ", ".join(
    f"{key}={value}" for key, value in TIME_MAPPER_HELP_CHOICES.items()
)


def serialize_time_delta(delta: timedelta | relativedelta) -> str:
    """Serialize the given ``delta`` back to its string representation in the parser."""
    if isinstance(delta, str):
        return delta

    if isinstance(delta, timedelta):
        delta = relativedelta(seconds=int(delta.total_seconds()))

    for key, value in vars(delta).items():
        if not value:
            continue

        key = next(k for k, v in TIME_MAPPER_HELP_CHOICES.items() if key.startswith(v))
        return f"{int(value)}{key}"


def deserialize_time_delta(value: str) -> timedelta | relativedelta:
    """Deserialize the given ``value`` to its relevant 'delta' object."""
    if isinstance(value, timedelta | relativedelta):
        return value

    match = re.match(r"(^\d+)(\D+$)", value)
    return TimeMapper(match.group(2))(match.group(1))


def setup() -> None:
    """Setup app-specific options for jsonargparse"""
    set_dumper("yaml", yaml_dump)

    register_type(
        date,
        serializer=lambda x: x.strftime("%Y-%m-%d"),
        deserializer=lambda x: datetime.strptime(x, "%Y-%m-%d"),
    )

    register_type(
        timedelta | relativedelta,
        serializer=serialize_time_delta,
        deserializer=deserialize_time_delta,
    )

    register_type(
        SensitiveString,
        serializer=SensitiveString,
        deserializer=SensitiveString,
    )
