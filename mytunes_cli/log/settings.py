from typing import ClassVar, Any

from pydantic import Field, field_serializer
from pydantic_core.core_schema import SerializerFunctionWrapHandler
from pydantic_settings_logging import LoggingSettings as _LoggingSettings, FilterConfig

from mytunes_cli._base import BaseSettings


class LoggingSettings(BaseSettings, _LoggingSettings):
    _default_filename: ClassVar[str] = "logging"
    _supported_extensions: ClassVar[tuple[str, ...]] = ("yaml", "yml", "json", "ini")
    _env_prefix: ClassVar[str] = "LOGGING_"

    compact: bool = Field(
        description="When true, never print additional empty new lines in the console.",
        default=False,
        exclude=True,
    )

    @field_serializer("filters", mode="wrap", check_fields=True)
    def _fix_class_key(
            self, config: dict[str, FilterConfig], handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        """Base package exports the class incorrectly. Fix key so custom classes can be instantiated as expected."""
        data = handler(config)
        for conf in data.values():
            if (key := "class") in conf:
                conf["()"] = conf.pop(key)
        return data
