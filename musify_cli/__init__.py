"""
Welcome to the Musify CLI
"""
from pathlib import Path

from musify import PROGRAM_OWNER_USER

PROGRAM_NAME = "Musify CLI"
__version__ = "0.1"
PROGRAM_URL = f"https://github.com/{PROGRAM_OWNER_USER}/{PROGRAM_NAME.replace(" ", "-").lower()}"

MODULE_ROOT: str = Path(__file__).parent.name
PACKAGE_ROOT: Path = Path(__file__).parent.parent
