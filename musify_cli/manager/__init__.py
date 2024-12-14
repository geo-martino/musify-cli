"""
A manager package processes the config parsed by the core parser,
handling creation and processing of various aspects of Musify objects.

The core principle of this package is that it should be the **only** object that runs operations on libraries,
accessing the relevant config objects as needed.
No other part of the program should ever need to access this config directly.
"""
from ._processor import MusifyProcessor
