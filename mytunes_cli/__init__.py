"""
Welcome to the MyTunes CLI
"""
from pathlib import Path

from mytunes import PROGRAM_OWNER_USER

PROGRAM_NAME = "MyTunes CLI"
__version__ = "0.1"
PROGRAM_URL = f"https://github.com/{PROGRAM_OWNER_USER}/{PROGRAM_NAME.replace(" ", "-").lower()}"

MODULE_ROOT: str = Path(__file__).parent.name
PACKAGE_ROOT: Path = Path(__file__).parent.parent
