"""
Helpers for extracting signature information from various objects using ``inspect``.
"""
import inspect
from collections.abc import Callable
from typing import Any

import docstring_parser


def get_default_args(func: Callable) -> dict[str, Any]:
    """Get all the available default parameters for the args in a given callable ``func``"""
    signature = inspect.signature(func)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }


def get_arg_descriptions(func: Callable) -> dict[str, Any]:
    """Get all the available arg descriptions for the args in a given callable ``func``"""
    docstring = docstring_parser.parse(func.__doc__)
    return {
        param.arg_name: param.description
        for param in docstring.params
    }
