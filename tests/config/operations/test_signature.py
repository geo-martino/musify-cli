import inspect

from musify_cli.config.operations.signature import get_default_args, get_arg_descriptions


class TestSignature:
    @staticmethod
    def _test_function_for_default_args_1(arg1, arg2: str, arg3: int, arg4):
        """
        This is a test description.

        :param arg1: Arg1 description v1.
        :param arg2: Arg2 description v1.
        :param arg3: Arg3 description v1.
        :param arg4: Arg4 description v1.
        """
        pass

    @staticmethod
    def _test_function_for_default_args_2(arg1, arg2: str, arg3: int = 3, arg4="4"):
        """
        This is a test description.

        :param arg1: Arg1 description v2.
        :param arg2: Arg2 description v2.
        :param arg3: Arg3 description v2.
        :param arg4: Arg4 description v2.
        """
        pass

    def test_get_default_args(self):
        defaults = get_default_args(self.test_get_default_args)
        assert defaults == {}

        defaults = get_default_args(self._test_function_for_default_args_1)
        assert defaults == {}

        defaults = get_default_args(self._test_function_for_default_args_2)
        assert defaults == {"arg3": 3, "arg4": "4"}

    def test_get_arg_descriptions(self):
        descriptions = get_arg_descriptions(self.test_get_arg_descriptions)
        assert descriptions == {}

        args = inspect.signature(self._test_function_for_default_args_1).parameters
        descriptions = get_arg_descriptions(self._test_function_for_default_args_1)
        assert descriptions == {arg: f"{arg.title()} description v1." for arg in args}

        args = inspect.signature(self._test_function_for_default_args_1).parameters
        descriptions = get_arg_descriptions(self._test_function_for_default_args_2)
        assert descriptions == {arg: f"{arg.title()} description v2." for arg in args}
