"""
Main driver of the program.

User can run 'python -m musify_cli ...' to access the program from this script.
"""
import logging
import os
import shutil
import sys
import traceback
from glob import glob
from os.path import join, isfile

from musify_cli import PROGRAM_NAME
from musify_cli.manager import MusifyManager
from musify_cli.parser import CORE_PARSER
from musify_cli.processor import MusifyProcessor
from musify_cli.printers import print_logo, print_line, print_time


def set_title(value: str) -> None:
    """Set the terminal title to given ``value``"""
    if sys.platform == "win32":
        os.system(f"title {value}")
    elif sys.platform == "linux" or sys.platform == "darwin":
        os.system(f"echo '\033]2;{value}\007'")


set_title(PROGRAM_NAME)
print()
print_logo()

if len(sys.argv) >= 2 and isfile(sys.argv[1]):
    config = CORE_PARSER.parse_path(sys.argv[1])
    functions = sys.argv[2:]
else:
    config = CORE_PARSER.parse_args()
    functions = config.functions

if config.logging.config_path and isfile(config.logging.config_path):
    MusifyManager.configure_logging(config.logging.config_path, config.logging.name, __name__)

manager = MusifyManager(config=config)
processor = MusifyProcessor(manager=manager)

# log the CLI header info
if processor.logger.file_paths:
    processor.logger.info(f"\33[90mLogs: {", ".join(processor.logger.file_paths)} \33[0m")
processor.logger.info(f"\33[90mOutput: {manager.output_folder} \33[0m")
processor.logger.print()
if manager.dry_run:
    print_line("DRY RUN ENABLED", " ")

processor.remote.api.authorise()

for i, func in enumerate(functions, 1):
    title = f"{PROGRAM_NAME}: {func}"
    if manager.dry_run:
        title += " (DRYRUN)"
    set_title(title)
    print_line(func)

    # TODO: need to add a step here for loading next function config and merging with manager

    try:  # run the functions requested by the user
        processor.set_processor(func)
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
