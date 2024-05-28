import string
from pathlib import Path
from random import randrange, choice

path_tests = Path(__file__).parent
path_root = path_tests.parent
path_resources = path_tests.joinpath("__resources")

path_txt = path_resources.joinpath("test").with_suffix(".txt")
path_logging_config = path_resources.joinpath("test_logging").with_suffix(".yml")


def random_str(start: int = 30, stop: int = 50) -> str:
    """Generates a random string of upper and lower case characters with a random length between the values given."""
    range_ = randrange(start=start, stop=stop) if start < stop else start
    return "".join(choice(string.ascii_letters) for _ in range(range_))
