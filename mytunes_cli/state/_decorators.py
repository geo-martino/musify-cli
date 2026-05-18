from collections.abc import Callable, Collection, Awaitable
from functools import partial, update_wrapper
from typing import Optional, Any

from mytunes.logger import Logger

from mytunes_cli.state.exception import LibraryStateError, StateError


# noinspection PyPep8Naming
class _state:
    """Base state manager."""
    def __new__(cls, *args, **kwargs):
        func: Optional[Callable] = next(
            (arg for arg in args if callable(arg) and not isinstance(arg, load_state)), None
        )
        self = partial(cls, *args, **kwargs) if func is None else super().__new__(cls)
        return update_wrapper(self, func)

    def __init__(self, func: Callable | None = None):
        self.func = func
        self.instance = None

    def __get__(self, instance, owner):
        self.instance = instance
        return self

    async def __call__(self, *args, **kwargs) -> Any:
        coro = self.func(self.instance, *args, **kwargs) if self.instance else self.func(*args, **kwargs)
        return await coro


# noinspection PyPep8Naming
class load_state[T](_state):
    """
    Decorator to manage library load state.

    This decorator only runs the function if it has not been run before
    and stores its state so that future calls return the same result, effectively working like a cache.

    We use this in conjunction with the save_state decorator which will clear this
    loaded state on its operation.

    We may also define a set of other load states which should be loaded before this one runs.
    Attempting to run this load state before those will result in an exception.
    """
    def __init__(
            self,
            func: Callable[Any, Awaitable[T]] = None,
            required_states: load_state | Collection[load_state] = (),
            set_states: load_state | Collection[load_state] = (),
    ):
        super().__init__(func)
        self.loaded = False
        self.result = None

        self.required_states = (required_states,) if isinstance(required_states, load_state) else required_states
        self.set_states = (set_states,) if isinstance(set_states, load_state) else set_states

    async def __call__(self, *args, **kwargs) -> T:
        if any(not state.loaded for state in self.required_states):
            required = [state.func.__name__ for state in self.required_states]
            raise LibraryStateError(
                "Cannot run this load operation as required upstream loads have not executed: " +
                Logger.format_list_to_string(required)
            )

        if not self.loaded:
            self.result = await super().__call__(*args, **kwargs)
            self.loaded = True

            for state in self.set_states:
                state.loaded = True

        return self.result

    def reset(self) -> None:
        self.loaded = False
        self.result = None


# noinspection PyPep8Naming
class save_state[T](_state):
    """
    Decorator to manage library save state.

    This wrapper manages the load state by resetting its cache whenever the function
    associated with this decorator is called.
    """
    def __init__(
            self,
            func: Callable | None = None,
            reset_states: load_state | Collection[load_state] = (),
    ):
        super().__init__(func)
        self.reset_states = (reset_states,) if isinstance(reset_states, load_state) else reset_states

        if not self.reset_states:
            raise StateError(
                "You must specify associated load states that will be reset by this save operation."
            )

    async def __call__(self, *args, **kwargs) -> Any:
        result = await super().__call__(*args, **kwargs)
        for state in self.reset_states:
            state.reset()
        return result
