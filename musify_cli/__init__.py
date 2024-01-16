from os.path import basename, dirname

from musify import PROGRAM_OWNER_USER

PROGRAM_NAME = "Musify CLI"
__version__ = "0.1"
PROGRAM_URL = f"https://github.com/{PROGRAM_OWNER_USER}/{PROGRAM_NAME.replace(" ", "-").lower()}"

MODULE_ROOT: str = basename(dirname(__file__))
PACKAGE_ROOT: str = dirname(dirname(__file__))
