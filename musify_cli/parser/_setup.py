"""
Operations for setting up the jsonargparse package for this program.
"""
from datetime import date, datetime

from jsonargparse.typing import register_type


def setup() -> None:
    """Setup app-specific options for jsonargparse"""
    register_type(
        date,
        serializer=lambda x: x.strftime("%Y-%m-%d") if isinstance(x, datetime) else x,
        deserializer=lambda x: datetime.strptime(x, "%Y-%m-%d") if isinstance(x, str) else x,
    )

    # TODO: add custom dumper for handling PrettyPrinter & Field objects
