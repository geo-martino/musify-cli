import string
from os.path import join, dirname
from random import randrange, choice

path_root = dirname(dirname(__file__))
path_tests = dirname(__file__)
path_resources = join(dirname(__file__), "__resources")

path_txt = join(path_resources, "test.txt")
path_logging_config = join(path_resources, "test_logging.yml")


def random_str(start: int = 30, stop: int = 50) -> str:
    """Generates a random string of upper and lower case characters with a random length between the values given."""
    range_ = randrange(start=start, stop=stop) if start < stop else start
    return "".join(choice(string.ascii_letters) for _ in range(range_))
