from unittest.mock import AsyncMock, Mock

import pytest
from faker import Faker

from mytunes_cli.state._decorators import load_state, save_state
from mytunes_cli.state.exception import LibraryStateError, StateError


@pytest.fixture
def mock_func(faker: Faker) -> Mock:
    async def func() -> str:
        return faker.uuid4()

    return AsyncMock(side_effect=func)


class TestLoadState:

    async def test_caches_result(self, mock_func: Mock, faker: Faker) -> None:
        wrapped_func = load_state(mock_func)

        for _ in range(faker.random_int(1, 5)):
            assert await wrapped_func() == await wrapped_func()
            mock_func.assert_called_once()

    async def test_skips_when_required_state_not_set(self, mock_func: Mock, faker: Faker):
        required_funcs = [load_state(AsyncMock()) for _ in range(faker.random_int(1, 5))]
        wrapped_func = load_state(mock_func, required_states=required_funcs)

        for _ in range(faker.random_int(1, 5)):
            with pytest.raises(LibraryStateError, match="required upstream"):
                await wrapped_func()
            mock_func.assert_not_called()

    async def test_sets_other_states(self, mock_func: Mock, faker: Faker):
        required_funcs = [load_state(AsyncMock()) for _ in range(faker.random_int(1, 5))]
        wrapped_func = load_state(mock_func, set_states=required_funcs)

        await wrapped_func()
        mock_func.assert_called_once()

        downstream_func = load_state(AsyncMock(), required_states=required_funcs)

        await downstream_func()  # shouldn't raise an error
        assert all(func.loaded for func in required_funcs)


class TestSaveState:

    async def test_resets_other_states(self, mock_func: Mock, faker: Faker):
        reset_funcs = [load_state(mock_func) for _ in range(faker.random_int(1, 5))]
        for func in reset_funcs:
            await func()

        mock_func.reset_mock()
        await next((func() for func in reset_funcs))
        mock_func.assert_not_called()

        mock_save_func = AsyncMock()
        wrapped_func = save_state(mock_save_func, reset_states=reset_funcs)

        await wrapped_func()

        await next((func() for func in reset_funcs))
        mock_func.assert_called_once()

    def test_fails_on_no_other_states(self, mock_func: Mock):
        with pytest.raises(StateError, match="reset"):
            save_state(mock_func)
