from os.path import join, dirname

path_root = dirname(dirname(__file__))
path_tests = dirname(__file__)
path_resources = join(dirname(__file__), "__resources")

path_txt = join(path_resources, "test.txt")
path_logging_config = join(path_resources, "test_logging.yml")
