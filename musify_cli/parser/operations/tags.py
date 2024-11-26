from functools import partial
from typing import Collection, Annotated

from aiorequestful.types import UnitCollection
from musify.field import TagField, Field, Fields, TagFields
from musify.libraries.local.track.field import LocalTrackField
from musify.utils import to_collection
from pydantic import BeforeValidator

from musify_cli.exception import ParserError

TAG_ORDER = [field.name.lower() for field in Fields.all()]
# noinspection PyTypeChecker
LOCAL_TRACK_TAG_NAMES: list[str] = list(sorted(
    set(LocalTrackField.__tags__), key=lambda x: TAG_ORDER.index(x)
))


def get_tags[T: TagField](
        tags: UnitCollection[str] | UnitCollection[T] | None, cls: type[T] = LocalTrackField
) -> tuple[T, ...]:
    """Get the :py:class:`Field` enums of the given ``cls`` for a given list of ``tags``"""
    if isinstance(tags, Collection) and all(v.__class__ == cls for v in tags):
        return to_collection(tags)
    if isinstance(tags, Collection) and not all(isinstance(v, str) for v in tags):
        raise ParserError("Unrecognised input type", value=tags)

    values = to_collection(tags, tuple)
    if not values or (isinstance(tags, Field) and tags.value == Fields.ALL):
        return tuple(cls.all(only_tags=True))

    tags = cls.to_tags(cls.from_name(*values))
    order = cls.all()
    return tuple(sorted(cls.from_name(*tags), key=lambda x: order.index(x)))


Tags = Annotated[
    LocalTrackField | tuple[LocalTrackField, ...],
    BeforeValidator(partial(get_tags, cls=TagFields))
]
LocalTrackFields = Annotated[
    LocalTrackField | tuple[LocalTrackField, ...],
    BeforeValidator(partial(get_tags, cls=LocalTrackField))
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
