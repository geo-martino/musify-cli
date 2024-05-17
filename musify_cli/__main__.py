"""
Main driver of the program.

User can run 'python -m musify_cli ...' to access the program from this script.
"""
import logging
import os
import shutil
import sys
import traceback
from argparse import ArgumentParser
from glob import glob
from os.path import join, isfile
from typing import Any

import yaml
from jsonargparse import Namespace
from musify.utils import merge_maps

from musify_cli import PROGRAM_NAME
from musify_cli.manager import MusifyManager
from musify_cli.parser import CORE_PARSER, LIBRARY_PARSER, load_library_config
from musify_cli.printers import print_logo, print_line, print_time, get_func_log_name
from musify_cli.processor import MusifyProcessor

# noinspection PyProtectedMember
CORE_PARSER._positionals.title = "Functions"

processor_method_names = [
    name.replace("_", "-") for name in MusifyProcessor.__new__(MusifyProcessor).__processormethods__
]
ArgumentParser.add_argument(
    CORE_PARSER, "functions", type=str, nargs="*", default=[],
    choices=processor_method_names, help=f"{PROGRAM_NAME} function to run."
)


DROP_KEYS_FROM_BASE_CONFIG: set[tuple[str]] = {
    ("filter",),
    ("backup",),
    ("pause",),
}


def load_config(config_path: str, *function_names: str) -> tuple[Namespace, dict[str, Namespace]]:
    """Load config from yaml file at ``config_path``, parsing config for all given ``function_names``

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


def set_title(value: str) -> None:
    """Set the terminal title to given ``value``"""
    if sys.platform == "win32":
        os.system(f"title {value}")
    elif sys.platform == "linux" or sys.platform == "darwin":
        os.system(f"echo '\033]2;{value}\007'")


set_title(PROGRAM_NAME)
print()
print_logo()

if any(arg in sys.argv for arg in ["-h", "--help"]):
    CORE_PARSER.print_help()
    exit()
elif len(sys.argv) >= 2 and isfile(sys.argv[1]):
    cfg_base, cfg_functions = load_config(*sys.argv[1:])
else:
    cfg_base = CORE_PARSER.parse_args()
    cfg_functions = {func: cfg_base for func in cfg_base.functions}

if cfg_base.logging.config_path and isfile(cfg_base.logging.config_path):
    MusifyManager.configure_logging(cfg_base.logging.config_path, cfg_base.logging.name, __name__)

manager = MusifyManager(config=cfg_base)
processor = MusifyProcessor(manager=manager)

# log the CLI header info
if processor.logger.file_paths:
    processor.logger.info(f"\33[90mLogs: {", ".join(processor.logger.file_paths)} \33[0m")
processor.logger.info(f"\33[90mOutput: {manager.output_folder} \33[0m")
processor.logger.print()
if manager.dry_run:
    print_line("DRY RUN ENABLED", " ")

processor.logger.debug("Base config:\n" + CORE_PARSER.dump(cfg_base))

for i, (name, config) in enumerate(cfg_functions.items(), 1):
    title = f"{PROGRAM_NAME}: {name}"
    if manager.dry_run:
        title += " (DRYRUN)"
    log_name = get_func_log_name(name)

    set_title(title)
    print_line(log_name)

    try:
        processor.set_processor(name, config)

        processor.logger.debug(f"{log_name} core config:\n" + CORE_PARSER.dump(config))
        processor.logger.debug(f"{log_name} local library config:\n" + LIBRARY_PARSER.dump(config.libraries.local))
        processor.logger.debug(f"{log_name} remote library config:\n" + LIBRARY_PARSER.dump(config.libraries.remote))

        processor.remote.api.authorise()
        processor()
    except (Exception, KeyboardInterrupt):
        processor.logger.critical(traceback.format_exc())
        break

if not glob(join(manager.output_folder, "*")):
    shutil.rmtree(manager.output_folder)

processor.logger.debug(f"Time taken: {processor.time_taken}")
logging.shutdown()

print_logo()
if processor.logger.file_paths:
    print(f"\33[90mLogs: {", ".join(processor.logger.file_paths)} \33[0m")
print(f"\33[90mOutput: {manager.output_folder} \33[0m")
print()
print_time(processor.time_taken)
