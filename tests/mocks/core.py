from abc import ABCMeta

from musify.libraries.core.object import Library


class LibraryMock(Library, metaclass=ABCMeta):

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def source(cls) -> str:
        """The type of local library loaded"""
        return super().source.replace("Mock", "")
