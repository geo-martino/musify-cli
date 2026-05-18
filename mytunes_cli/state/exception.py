from mytunes.exception import MyTunesError


class StateError(MyTunesError):
    """Exception raised for an invalid state."""


class LibraryStateError(StateError):
    """Exception raised for an invalid load/save library state."""
