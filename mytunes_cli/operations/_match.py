from abc import abstractmethod
from collections.abc import Sequence

from mytunes.annotation import ResourceModel
from mytunes.core.collection import CollectionModel
from mytunes.processors.check import ItemChecker, CollectionChecker
from mytunes.processors.clean.string import NameCleaner
from mytunes.processors.search import ItemSearcher, CollectionSearcher
from pydantic import Field

from mytunes_cli.operations._base import RemoteAPIOperation


# noinspection PyAbstractClass
class Match[CT: CollectionModel, IT: ResourceModel](RemoteAPIOperation):
    async def run(self) -> None:
        matched = await self._match()
        await self._save(matched)

    @property
    @abstractmethod
    def items(self) -> Sequence[CT]:
        """The items to process."""
        raise NotImplementedError

    @abstractmethod
    async def _match(self) -> Sequence[IT]:
        raise NotImplementedError

    @abstractmethod
    async def _save(self, items: Sequence[IT]) -> None:
        raise NotImplementedError

    def _log_empty_results(self) -> tuple:
        message = "[red]No items matched[/]"
        self._logger.warning(message, new_line_start=True)
        return tuple()


# noinspection PyAbstractClass
class ItemSearch[IT: ResourceModel](Match[IT, IT], ItemSearcher):
    # TODO: remove on aiorequestful v2?
    cleaner: NameCleaner | None = Field(
        description=(
            "The cleaner to use for cleaning the query parameters generated for an item. "
            "If None, no cleaning will be done. "
            "This doesn't apply to the query string passed to the query method, which is always used as-is."
        ),
        default=None,
    )

    @property
    def result_key(self) -> str:
        """The key to use when logging results."""
        raise NotImplementedError

    async def _match(self) -> Sequence[IT]:
        self.api.search.cleaner = self.cleaner

        result = await self.search_many(self.items, name=self.result_key)
        if not result:
            return self._log_empty_results()

        self.log_results(result)
        return tuple(result.matched)


# noinspection PyAbstractClass
class CollectionSearch[CT: CollectionModel, IT: ResourceModel](Match[CT, IT], CollectionSearcher):
    # TODO: remove on aiorequestful v2?
    cleaner: NameCleaner | None = Field(
        description=(
            "The cleaner to use for cleaning the query parameters generated for an item. "
            "If None, no cleaning will be done. "
            "This doesn't apply to the query string passed to the query method, which is always used as-is."
        ),
        default=None,
    )

    async def _match(self) -> tuple[IT, ...]:
        self.api.search.cleaner = self.cleaner

        results = await self.search_many(self.items)
        if not results:
            return self._log_empty_results()

        self.log_results(results)

        matched = []
        for result in results:
            for item in result.matched:
                if item not in matched:
                    matched.append(item)

        return tuple(matched)


# noinspection PyAbstractClass
class ItemCheck[IT: ResourceModel](Match[IT, IT], ItemChecker):
    @property
    def result_key(self) -> str:
        """The key to use when logging results."""
        raise NotImplementedError

    async def _match(self) -> Sequence[IT]:
        result = await self.check(self.items, name=self.result_key)
        if not result:
            return self._log_empty_results()

        self.log_results(result)
        return tuple(list(result.changed) + list(result.unavailable))


# noinspection PyAbstractClass
class CollectionCheck[CT: CollectionModel, IT: ResourceModel](Match[CT, IT], CollectionChecker):
    async def _match(self) -> tuple[IT, ...]:
        results = await self.check_on_playlists(self.items)
        if not results:
            return self._log_empty_results()

        self.log_results(results)

        changed = []
        for result in results:
            for item in list(result.changed) + list(result.unavailable):
                if item not in changed:
                    changed.append(item)

        return tuple(changed)
