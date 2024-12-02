from abc import ABCMeta

from musify.libraries.core.object import Library
from musify.utils import classproperty


class LibraryMock(Library, metaclass=ABCMeta):

    # noinspection PyMethodParameters
    @classproperty
    def source(cls) -> str:
        """The type of local library loaded"""
        return super().source.replace("Mock", "")
