from abc import ABCMeta
from typing import Type, Any, Self, Mapping

from musify.processors.filter import FilterComparers
from pydantic import BaseModel, Field

from musify_cli.exception import ParserError
from musify_cli.parser.operations.filters import Filter


class PlaylistsConfig(BaseModel):
    filter: Filter = Field(
        description="The filter to apply to available playlists. Filters on playlist names",
        default=FilterComparers(),
    )


class LibraryConfig(BaseModel, metaclass=ABCMeta):
    _type_map: dict[str, Type[BaseModel]]

    name: str = Field(
        description="The user-assigned name of this library",
    )
    type: str = Field(
        description="The source type of this library",
    )
    playlists: PlaylistsConfig = Field(
        description="Configures handling for this library's playlists",
        default=PlaylistsConfig()
    )

    # noinspection PyUnresolvedReferences
    @classmethod
    def create_and_determine_library_type(cls, kwargs: Any | Self) -> Self:
        """
        Create a new :py:class:`.Library` object and determine its type dynamically from the given ``config``
        """
        if not isinstance(kwargs, Mapping):
            return kwargs

        library_type = kwargs.get(type_key := "type", "").strip().casefold()
        if library_type not in cls._type_map.default:
            raise ParserError("Unrecognised library type", key=type_key, value=library_type)

        sub_type = cls._type_map.default[library_type]
        return cls[sub_type](**kwargs)
