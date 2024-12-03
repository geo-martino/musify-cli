from collections.abc import Collection
from functools import partial
from typing import Annotated

from aiorequestful.types import UnitCollection
from musify.field import TagField, Field, Fields, TagFields
from musify.libraries.local.track.field import LocalTrackField
from musify.utils import to_collection
from pydantic import BeforeValidator, PlainSerializer

from musify_cli.exception import ParserError

FIELD_NAMES = [field.name.lower() for field in Fields.all()]
TAG_NAMES = [field.name.lower() for field in TagFields.all()]
# noinspection PyTypeChecker
LOCAL_TRACK_TAG_NAMES: list[str] = list(sorted(
    set(LocalTrackField.__tags__), key=lambda x: FIELD_NAMES.index(x)
))

type TagConfigType[T: TagField] = UnitCollection[str] | UnitCollection[T] | None


def get_tags[T: TagField](tags: TagConfigType[T], cls: type[T] = LocalTrackField) -> tuple[T, ...]:
    """Get the :py:class:`Field` enums of the given ``cls`` for a given list of ``tags``"""
    if isinstance(tags, Collection) and all(v.__class__ == cls for v in tags):
        return to_collection(tags)
    if isinstance(tags, Collection) and not all(isinstance(v, str) for v in tags):
        raise ParserError("Unrecognised input type", value=tags)

    values = to_collection(tags, tuple)
    if not values or (isinstance(tags, Field) and tags.value == Fields.ALL):
        return tuple(cls.all(only_tags=True))

    order = cls.all()
    return tuple(sorted(cls.from_name(*values), key=lambda x: order.index(x)))


def serialise_tags(fields: UnitCollection[TagField]) -> list[str]:
    """Get the field names from a collection of :py:class:`Field` enums"""
    return [field.name.lower() for field in to_collection(fields)]


Tags = Annotated[
    TagField | tuple[TagField, ...],
    BeforeValidator(partial(get_tags, cls=TagFields)),
    PlainSerializer(serialise_tags, when_used="json-unless-none"),
]
LocalTrackFields = Annotated[
    LocalTrackField | tuple[LocalTrackField, ...],
    BeforeValidator(partial(get_tags, cls=LocalTrackField)),
    PlainSerializer(serialise_tags, when_used="json-unless-none"),
]


def get_tag_filter(config: dict[str, str | tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Validate and reformat the given tag filter ``config``."""
    for tag, value in config.items():
        if tag not in LOCAL_TRACK_TAG_NAMES:
            raise ParserError(f"Unrecognised {tag=}")
        if not value:
            raise ParserError(f"No value given for {tag=}")

        config[tag] = tuple(str(v) for v in to_collection(value))

    return config


TagFilter = Annotated[dict[str, tuple[str, ...]], BeforeValidator(get_tag_filter)]
