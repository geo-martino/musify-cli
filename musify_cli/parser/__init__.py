"""
Sets up and configures the parser/s for this program.
"""
from ._core import CORE_PARSER, load_library_config
from ._library import LIBRARY_PARSER, LOCAL_LIBRARY_TYPES, REMOTE_LIBRARY_TYPES
from ._utils import LoadTypesLocal, LoadTypesRemote, EnrichTypesRemote

LIBRARY_TYPES = {t.lower() for t in LOCAL_LIBRARY_TYPES + REMOTE_LIBRARY_TYPES}
