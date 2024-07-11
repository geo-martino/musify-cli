"""
Main driver of the program.

User can run 'python -m musify_cli ...' to access the program from this script.
"""
import asyncio
import logging
import os
import shutil
import sys
import traceback
from argparse import ArgumentParser
from asyncio import AbstractEventLoop
from pathlib import Path
from typing import Any

import yaml
from jsonargparse import Namespace
from musify.utils import merge_maps

from musify_cli import PROGRAM_NAME, MODULE_ROOT
from musify_cli.exception import ParserError
from musify_cli.manager import MusifyManager
from musify_cli.parser import CORE_PARSER, LIBRARY_PARSER, load_library_config
from musify_cli.printers import print_logo, print_line, print_time, get_func_log_name
from musify_cli.processor import MusifyProcessor

LOGGER = logging.getLogger(MODULE_ROOT)

# noinspection PyProtectedMember
CORE_PARSER._positionals.title = "Functions"

PROCESSOR_METHOD_NAMES = [
    name.replace("_", "-") for name in MusifyProcessor.__new__(MusifyProcessor).__processormethods__
]
ArgumentParser.add_argument(
    CORE_PARSER, "functions", type=str, nargs="*", default=[],
    choices=PROCESSOR_METHOD_NAMES, help=f"{PROGRAM_NAME} function to run."
)

DROP_KEYS_FROM_BASE_CONFIG: set[tuple[str]] = {
    ("filter",),
    ("backup",),
    ("pause",),
}


###########################################################################
## Printers and terminal setters
###########################################################################
def set_title(value: str) -> None:
    """Set the terminal title to given ``value``"""
    if sys.platform == "win32":
        os.system(f"title {value}")
    elif sys.platform == "linux" or sys.platform == "darwin":
        os.system(f"echo -n '\033]2;{value}\007'")


def print_header() -> None:
    """Print header text to the terminal."""
    set_title(PROGRAM_NAME)
    print()
    print_logo()


def print_folders(processor: MusifyProcessor):
    """Print the key folder locations to the terminal"""
    if processor.logger.file_paths:
        processor.logger.info(f"\33[90mLogs: {", ".join(map(str, set(processor.logger.file_paths)))} \33[0m")
    processor.logger.info(f"\33[90mOutput: {processor.manager.output_folder} \33[0m")
    print()


def print_sub_header(processor: MusifyProcessor) -> None:
    """Print sub-header text to the terminal."""
    print_folders(processor)
    if processor.manager.dry_run:
        print_line("DRY RUN ENABLED", " ")


def print_function_header(name: str, processor: MusifyProcessor) -> str:
    """Set the terminal title and print the function header to the terminal."""
    title = f"{PROGRAM_NAME}: {name}"
    if processor.manager.dry_run:
        title += " (DRYRUN)"

    name = get_func_log_name(name)
    set_title(title)
    print_line(name)

    return name


###########################################################################
## Config and setup
###########################################################################
def setup() -> tuple[Namespace, dict[str, Namespace]]:
    """Get config and configure logger."""
    if any(arg in sys.argv for arg in ["-h", "--help"]):
        CORE_PARSER.print_help()
        exit()
    elif len(sys.argv) >= 2 and os.path.isfile(sys.argv[1]):
        cfg_base, cfg_functions = load_config(*sys.argv[1:])
    else:
        cfg_base = CORE_PARSER.parse_args()
        cfg_functions = {func: cfg_base for func in cfg_base.functions}

    if cfg_base.logging.config_path:
        path = Path(cfg_base.logging.config_path)
        if path.is_file():
            MusifyManager.configure_logging(path, cfg_base.logging.name, __name__)

    check_config_is_valid(cfg_functions)
    return cfg_base, cfg_functions


def load_config(config_path: str | Path, *function_names: str) -> tuple[Namespace, dict[str, Namespace]]:
    """
    Load config from yaml file at ``config_path``, parsing config for all given ``function_names``

    :return: Loaded base config and the loaded functions' config.
    """
    with open(config_path, "r", encoding="utf-8") as file:
        data = yaml.full_load(file)
    functions_data = data.pop("functions", {})
    base = CORE_PARSER.parse_object(data)

    for keys in DROP_KEYS_FROM_BASE_CONFIG:
        d = data
        for key in keys[:-1]:
            d = d.get(key, {})
        d.pop(keys[-1], None)

    libraries = data.pop("libraries", {})

    def _merge_library(name: str, f_data: dict[str, Any]) -> None:
        overwrite = None
        new = f_data.get("libraries", {}).get(name)
        if isinstance(new, dict):
            overwrite = {base.libraries.get(name).type: new}
        elif isinstance(new, str):
            overwrite = new
        f_data["libraries"][name] = load_library_config(
            lib=libraries[name],
            config_path=libraries.get("config_path"),
            overwrite=overwrite,
        )

    for func_data in functions_data.values():
        func_data["libraries"] = func_data.get("libraries", {})
        _merge_library("local", func_data)
        _merge_library("remote", func_data)

        merge_maps(func_data, data, extend=False, overwrite=True)

    functions = {
        func: base if func.replace("-", "_") not in functions_data else
        CORE_PARSER.parse_object(functions_data[func.replace("-", "_")])
        for func in function_names
    }

    return base, functions


def dump_config(name: str, processor: MusifyProcessor) -> None:
    """Dump/log the current config."""
    config = processor.manager.config

    processor.logger.debug(f"{name} core config:\n" + CORE_PARSER.dump(config))

    local_config_dump = LIBRARY_PARSER.dump(config.libraries.local)
    processor.logger.debug(f"{name} local library config:\n{local_config_dump}")

    remote_config_dump = LIBRARY_PARSER.dump(config.libraries.remote)
    processor.logger.debug(f"{name} remote library config:\n{remote_config_dump}")


def check_config_is_valid(config: dict[str, Namespace]) -> None:
    """Run validity checks against given loaded ``config``"""
    if not config:
        message = "No function specified"
        LOGGER.debug(message)
        print_line(message.upper())
        exit(0)

    unknown_functions = [func for func in config if func not in PROCESSOR_METHOD_NAMES]
    if unknown_functions:
        print(
            "Did not recognise some of the given function names.",
            f"Choose from the following: {", ".join(PROCESSOR_METHOD_NAMES)}"
        )
        raise ParserError("Invalid function names given", key="functions", value=unknown_functions)


###########################################################################
## Core
###########################################################################
async def main(processor: MusifyProcessor, config: dict[str, Namespace]) -> None:
    """Main driver for CLI operations."""
    dump_config("Base", processor)

    for i, (name, cfg) in enumerate(config.items(), 1):
        log_name = print_function_header(name, processor)

        async with processor:
            processor.set_processor(name, cfg)
            dump_config(log_name, processor)

            await processor.manager.run_pre()
            await processor
            if name != next(reversed(config)):  # only run post up to penultimate function
                await processor.manager.run_post()

            processor.logger.print_line()


# noinspection PyUnusedLocal
def handle_exception(lp: AbstractEventLoop, context: dict[str, Any]) -> None:
    """Handle exceptions from a given ``loop``"""
    lp.stop()


def close(processor: MusifyProcessor) -> None:
    """Close the ``processor`` and log closing messages."""
    if not processor.manager.output_folder.glob("*"):
        shutil.rmtree(processor.manager.output_folder)

    print_header()
    processor.logger.debug(f"Time taken: {processor.time_taken}")
    logging.shutdown()

    print_folders(processor)
    print_time(processor.time_taken)
    print()


if __name__ == "__main__":
    print_header()
    config_base, config_functions = setup()

    main_processor = MusifyProcessor(manager=MusifyManager(config=config_base))
    print_sub_header(main_processor)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(handle_exception)

    task = loop.create_task(main(main_processor, config_functions))
    try:
        loop.run_until_complete(task)
    except (Exception, KeyboardInterrupt):
        main_processor.logger.debug(traceback.format_exc())
        print(f"\33[91m{traceback.format_exc(0)}\33m")
        sys.exit(1)
    finally:
        close(main_processor)
