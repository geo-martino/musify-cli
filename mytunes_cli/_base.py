import json
from collections.abc import MutableMapping
from functools import wraps
from pathlib import Path
from typing import ClassVar, Any

import yaml
from mytunes import PROGRAM_NAME
# noinspection PyProtectedMember
from mytunes._base import BaseModel
# noinspection PyProtectedMember
from mytunes._types import get_base_types
from pydantic import model_validator
from pydantic_settings import BaseSettings as PydanticBaseSettings, SettingsConfigDict, PydanticBaseSettingsSource, \
    JsonConfigSettingsSource, CliSubCommand, CliApp
# noinspection PyProtectedMember
from pydantic_settings_logging import IniConfigSettingsSource, TomlConfigSettingsSource

from ._io.yaml import MultiFileYamlConfigSettingsSource


class BaseSettings(
    PydanticBaseSettings,
    BaseModel,
    cli_prog_name=PROGRAM_NAME,
    cli_implicit_flags="toggle",
    cli_hide_none_type=True,
    cli_kebab_case=True,
    cli_avoid_json=True,
):
    """Wrapper for defining common config for settings in the package."""
    _default_filename: ClassVar[str | None] = None
    _supported_extensions: ClassVar[tuple[str, ...]] = ()

    model_config = SettingsConfigDict(
        env_prefix="MYTUNES_",
        validate_default=True,
        validate_assignment=True,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
    )

    def __new__(cls, *, env_prefix: str = model_config["env_prefix"], config_path: str | Path | None = None, **kwargs):
        """
        Create settings with custom configuration sources.

        Args:
            env_prefix: Environment variable prefix
            config_path: Path to configuration file
        """
        # If custom parameters are provided, create a dynamic class
        if env_prefix != cls.model_config["env_prefix"] or config_path is not None:
            class CustomSettings(BaseSettings):
                model_config = SettingsConfigDict(
                    env_prefix=env_prefix,
                    env_nested_delimiter="__",
                    case_sensitive=False,
                    extra="allow",
                )

                @classmethod
                def settings_customise_sources(
                        cls,
                        settings_cls: type[BaseSettings],
                        init_settings: PydanticBaseSettingsSource,
                        env_settings: PydanticBaseSettingsSource,
                        dotenv_settings: PydanticBaseSettingsSource,
                        file_secret_settings: PydanticBaseSettingsSource,
                ) -> tuple[PydanticBaseSettingsSource, ...]:
                    # Add sources in reverse priority order (first source has the highest priority)
                    # Priority: init_settings > env > files

                    sources = [init_settings, env_settings, dotenv_settings, file_secret_settings]
                    if not config_path:
                        pass

                    # Add custom file sources
                    elif (path := Path(config_path)).is_file():
                        sources.append(cls._get_source_for_path(settings_cls, path))

                    elif (path := Path(config_path)).is_dir() and cls._default_filename:
                        path = path.joinpath(cls._default_filename)
                        for ext in cls._supported_extensions:
                            if (path := path.with_suffix("." + ext.lstrip("."))).is_file():
                                sources.append(cls._get_source_for_path(settings_cls, path))

                    if cls._default_filename:
                        path = Path(cls._default_filename)
                        for ext in cls._supported_extensions:
                            if (path := path.with_suffix("." + ext.lstrip("."))).is_file():
                                sources.append(cls._get_source_for_path(settings_cls, path))

                    # Add pyproject.toml source (lowest priority file)
                    if "toml" in cls._supported_extensions and (path := Path("pyproject.toml")).is_file():
                        table = ["tool", cls._default_filename]
                        sources.append(TomlConfigSettingsSource(settings_cls, toml_file=str(path), toml_table=table))

                    return tuple((source for source in sources if source is not None))

            # Use the custom class instead
            kls = type(cls.__name__, (cls, CustomSettings,), {})
            return super(BaseSettings, kls).__new__(kls)

        # Use the default class
        return super().__new__(cls)

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customise settings sources to load from multiple files."""
        # Add sources in reverse priority order (first source has the highest priority)
        # Priority: init_settings > env > files
        sources = [init_settings, env_settings, dotenv_settings, file_secret_settings]

        if cls._default_filename:
            path = Path(cls._default_filename)
            for ext in cls._supported_extensions:
                if (path := path.with_suffix("." + ext.lstrip("."))).is_file():
                    sources.append(cls._get_source_for_path(settings_cls, path))

        if "toml" in cls._supported_extensions and (path := Path("pyproject.toml")).is_file():
            table = ["tool", cls._default_filename]
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=str(path), toml_table=table))

        return tuple((source for source in sources if source is not None))

    @classmethod
    def _get_source_for_path(
            cls, settings_cls: type[BaseSettings], path: Path
    ) -> PydanticBaseSettingsSource | None:
        match path.suffix.lstrip("."):
            case "yml" | "yaml":
                return MultiFileYamlConfigSettingsSource(settings_cls, yaml_file=str(path))
            case "json":
                return JsonConfigSettingsSource(settings_cls, json_file=str(path))
            case "ini":
                return IniConfigSettingsSource(settings_cls, ini_file=str(path))
            case _:
                return None

    @wraps(PydanticBaseSettings.model_dump_json)
    def model_dump_yaml(self, **kwargs) -> str:
        """Generates a JSON representation of the model using ``yaml.safe_dump``."""
        data = json.loads(self.model_dump_json(**kwargs))
        return yaml.safe_dump(data, indent=2, default_flow_style=False, allow_unicode=True, sort_keys=False)


class BaseCommand(BaseSettings):
    @model_validator(mode="before")
    @classmethod
    def _set_state_on_subcommands[T](cls, data: T | MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        from mytunes_cli.state import HasGlobalState  # avoid circular import
        if not isinstance(data, MutableMapping):
            return data

        key = "state"
        state = data.get(key) if issubclass(cls, HasGlobalState) else data.pop(key, None)
        return cls._set_value_on_subcommands(data, key, state)

    @model_validator(mode="before")
    @classmethod
    def _set_printer_on_subcommands[T](cls, data: T | MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        from mytunes_cli.printer import HasPrinter  # avoid circular import
        if not isinstance(data, MutableMapping):
            return data

        key = "printer"
        printer = data.get(key) if issubclass(cls, HasPrinter) else data.pop(key, None)
        return cls._set_value_on_subcommands(data, key, printer)

    @classmethod
    def _set_value_on_subcommands[T: MutableMapping[str, Any]](cls, data: T, key: str, value: Any) -> T:
        if not value:
            return data

        for name, field in cls.model_fields.items():
            if CliSubCommand.__metadata__[0] not in field.metadata:
                continue
            if name not in data or not isinstance(data[name], MutableMapping):
                continue
            if key in data[name]:
                continue
            if not any(
                issubclass(kls, BaseCommand) or key in kls.model_fields for kls in get_base_types(field.annotation)
            ):
                continue

            data[name][key] = value

        return data

    @model_validator(mode="before")
    @classmethod
    def _set_unset_subcommands_as_null[T](cls, data: T | MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping):
            return data

        # needed to ensure commands can be parsed by pipeline command
        return {
            name: None for name, field in cls.model_fields.items()
            if CliSubCommand.__metadata__[0] in field.metadata
        } | dict(data)

    def cli_cmd(self) -> None:
        """Run the CLI command."""
        CliApp.run_subcommand(self)
