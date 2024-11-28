"""
A manager processes the config parsed by the core parser,
handling creation and processing of various aspects of Musify objects.

The core principle of a manager is that it should be the **only** object that processes the parsed config.
No other part of the program should ever need to access this config directly.
"""
from ._processor import MusifyProcessor
