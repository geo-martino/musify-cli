from collections.abc import Collection, Mapping
from contextlib import suppress

from mytunes.annotation import ResourceModel, StrippedString
from mytunes.core.api import ItemReadEndpoints
from mytunes.core.api.search import HasSearchEndpoints
from mytunes.core.collection import RemoteCollection
from mytunes.core.properties.logger import HasProgress
from mytunes.core.properties.uri import URI
from mytunes.exception import APIError
from mytunes.processors import InputProcessor, OptionsProcessor
from mytunes.processors.formatter import ModelFormatter, CollectionFormatter
from pydantic import Field, ValidationError, field_validator

from mytunes_cli.operations._base import Operation, RemoteAPIOperation


class Pause(Operation, InputProcessor):
    message: StrippedString = Field(
        description="The message to display in the pause.",
        default="Press enter to continue."
    )

    async def run(self) -> None:
        self._get_user_input(self.message)


class Print(RemoteAPIOperation, OptionsProcessor, HasProgress):
    formatter: ModelFormatter = Field(
        description="Format the output of the API call.",
        default=CollectionFormatter(
            fields=("Name", "Artist", "Album", "Length", "Released At", "Public URL"),
            styles=("white", "blue", "blue", "red", "yellow", "blue"),
            widths=(30, 20, 30, None, None, None),
            truncate=True,
            header=True,
        )
    )
    type: StrippedString | None = Field(
        description="The type of item to print. Only used when searching for items.",
        default=None,
    )
    collection_items: bool = Field(
        description="Always attempt to print the items of a collection.",
        default=False,
    )
    always_prompt: bool = Field(
        description=(
            "Whether to keep asking for input. "
            "If True, will keep asking for another value until the user manually quits. "
            "If False, quit after the first successful print."
        ),
        default=False,
    )

    @field_validator("formatter", mode="before", check_fields=True)
    @classmethod
    def _validate_formatter_from_fields[T](cls, data: T | Collection[str]) -> T | ModelFormatter:
        if isinstance(data, Mapping):
            return data
        if not isinstance(data, Collection) or not all(isinstance(field, str) for field in data):
            return data
        return ModelFormatter(fields=data, header=True)

    @property
    def _options(self) -> dict[str, str]:
        options = {
            "<URI>": f"The URI of the item to print info about.",
            "<URL>": f"The URL (api or public) of the item to print info about.",
            "<SEARCH>": "A value to search for. Prints the first result if found."
        }
        if self.always_prompt:
            options["<Return/Enter>"] = f"Stop asking for input and leave {type(self).__name__}."
        return options

    async def run(self) -> None:
        with self._pause_progress():
            await self.pause()

    async def pause(self) -> None:
        self._print_help_text()

        while option := self._get_user_input("Enter a value"):
            match option:
                case "":
                    return

                case _ if uri := self._create_uri(option):
                    printed = await  self._from_uri(uri)
                    if not printed or self.always_prompt:
                        continue
                    break

                case str() as query:
                    printed = await self._from_search(query)
                    if not printed or self.always_prompt:
                        continue
                    break

    def _create_uri(self, value: str | None) -> URI | None:
        with suppress(ValidationError):
            return self.api.create_uri(value=value)
        return None

    def _log_warning(self, message) -> None:
        self._logger.warning(f"[red]{message}[/]")

    async def _from_uri(self, uri: URI) -> bool:
        try:
            api = getattr(self.api, uri.type.rstrip("s") + "s", None)
            api = ItemReadEndpoints.validate_api(api, uri.type)
        except APIError as exc:
            self._log_warning(str(exc))
            return False

        item = await api.get(uri)
        if item is None:
            self._log_warning(f"No response for URI: {str(uri)!r}")
            return False

        return await self._print_item(item)

    async def _from_search(self, query: str) -> bool:
        try:
            api = HasSearchEndpoints.validate_api(self.api)
        except APIError as exc:
            self._log_warning(str(exc))
            return False

        item_kind = self.type.rstrip("s") if self.type else None
        while item_kind is None:
            item_kind = self._get_user_input("Enter an item type", choices=sorted(api.supported_search_types))
            if not item_kind:
                self._logger.debug(f"User skipped search: {query!r}")
                return False

        result = await api.query(query, types={item_kind}, limit=1)
        if not result or (item := next(iter(result.get(item_kind, ())), None)) is None:
            self._log_warning(f"No search results for query: {query!r}")
            return False

        if not self.collection_items:
            return await self._print_item(item)
        # attempt to get the full collection by getting the item again
        return await self._from_uri(item.uri) or await self._print_item(item)

    async def _print_item(self, item: ResourceModel) -> bool:
        if isinstance(item, RemoteCollection) and self.collection_items:
            await item.extend(self.api)

        table = self.formatter.format(item)
        self._logger.print(table)
        self._logger.print()
        return True
