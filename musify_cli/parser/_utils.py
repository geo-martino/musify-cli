"""
Utilities relating to all parsers in this program.
"""
import argparse
import inspect
from collections.abc import Collection, Mapping, Callable
from typing import Any, TypeVar

from jsonargparse import DefaultHelpFormatter
from musify.core.base import MusifyObject
from musify.core.enum import Fields, TagField, TagFields, MusifyEnum
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.compare import Comparer
from musify.processors.filter import FilterComparers
from musify.types import UnitCollection
from musify.utils import to_collection

from musify_cli.exception import ParserError

UT = TypeVar("UT")
MultiType = UnitCollection[UT] | Mapping[str, UnitCollection[UT]]

TAG_ORDER = [field.name.lower() for field in Fields.all()]
# noinspection PyTypeChecker
LOCAL_TRACK_TAG_NAMES: list[str] = list(sorted(
    set(LocalTrackField.__tags__), key=lambda x: TAG_ORDER.index(x)
))


###########################################################################
## Formatters
###########################################################################
class EpilogHelpFormatter(DefaultHelpFormatter):
    def _format_text(self, text) -> str:
        if text.startswith("==FORMATTED=="):
            return text.replace("==FORMATTED==", "")
        # noinspection PyProtectedMember
        return super()._format_text(text)

    def add_text(self, text: str | None) -> None:
        """Adds text to the final help text"""
        if text is not argparse.SUPPRESS and text is not None:
            self._add_item(self._format_text, [text])


###########################################################################
## Utility functions
###########################################################################
def get_default_args(func: Callable) -> dict[str, Any]:
    """Get all the available default parameters for the args in a given callable ``func``"""
    signature = inspect.signature(func)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }


###########################################################################
## Type functions
###########################################################################
def get_tags[T: TagField](
        tags: UnitCollection[str] | UnitCollection[T] | None, cls: type[T] = LocalTrackField
) -> tuple[T, ...]:
    """Get the :py:class:`Field` enums of the given ``cls`` for a given list of ``tags``"""
    if isinstance(tags, Collection) and all(v.__class__ == cls for v in tags):
        return to_collection(tags)
    if isinstance(tags, Collection) and not all(isinstance(v, str) for v in tags):
        raise ParserError("Unrecognised input type", value=tags)

    values = to_collection(tags, tuple)
    if not values or (isinstance(tags, TagField) and tags.value == TagFields.ALL):
        return tuple(cls.all(only_tags=True))

    tags = cls.to_tags(cls.from_name(*values))
    order = cls.all()
    return tuple(sorted(cls.from_name(*tags), key=lambda x: order.index(x)))


def get_comparers_filter[T](config: MultiType[T]) -> FilterComparers[T | MusifyObject]:
    """Generate the :py:class:`FilterComparers` object from the ``config``"""
    match_all = get_default_args(FilterComparers)["match_all"]
    if isinstance(config, Mapping):
        comparers = [
            Comparer(condition=cond, expected=exp) for cond, exp in config.items() if cond != "match_all"
        ]
        match_all = config.get("match_all", match_all)
    elif isinstance(config, str):
        comparers = Comparer(condition="is", expected=config)
    else:
        comparers = Comparer(condition="is in", expected=config)

    filter_ = FilterComparers(comparers=comparers, match_all=match_all)
    filter_.transform = lambda value: value.name if isinstance(value, MusifyObject) else value
    return filter_


###########################################################################
## Type enums
###########################################################################
class LoadTypesLocal(MusifyEnum):
    tracks = 0
    playlists = 1


class LoadTypesRemote(MusifyEnum):
    playlists = 1
    saved_tracks = 10
    saved_albums = 11
    saved_artists = 12


class EnrichTypesRemote(MusifyEnum):
    tracks = 0
    albums = 1
    artists = 2
