"""
Main driver of the program.

User can run 'python -m musify_cli ...' to access the program from this script.
"""
import asyncio
import logging
import sys
import traceback
from collections.abc import Collection

from musify_cli import MODULE_ROOT
from musify_cli.cli import PARSER
from musify_cli.config.core import MusifyConfig
from musify_cli.manager import MusifyProcessor
from musify_cli.printers import print_line, print_time, print_header, print_folders, print_function_header, \
    print_sub_header

LOGGER = logging.getLogger(MODULE_ROOT)


###########################################################################
## Config and setup
###########################################################################
def setup() -> tuple[MusifyConfig, dict[str, MusifyConfig]]:
    """Parse args + config and configure logger."""
    parsed_args = PARSER.parse_args()

    LOGGER.debug(f"Loading config from: {parsed_args.config}")
    base, functions = MusifyConfig.from_file(parsed_args.config)
    print(base.model_dump_yaml())
    for func in functions.values():
        print(func.model_dump_yaml())
        print("---------------------")

    if func_names := parsed_args.functions:
        func_names = {name.replace("-", "_") for name in func_names}
        functions = {name: conf for name, conf in functions.items() if name in func_names}
    check_config_is_valid(functions.values())

    base.logging.configure_additional_loggers(__name__)
    base.logging.configure_rotating_file_handler_dt(dt=base.paths.dt)
    base.logging.configure_logging()

    return base, functions


def check_config_is_valid(functions: Collection[MusifyConfig]) -> None:
    """Run validity checks against given loaded ``config``"""
    if not functions:
        message = "No function specified"
        LOGGER.debug(message)
        print_line(message.upper())
        exit(0)


###########################################################################
## Core
###########################################################################
async def main(processor: MusifyProcessor, config: dict[str, MusifyConfig]) -> None:
    """Main driver for CLI operations."""
    for i, (name, cfg) in enumerate(config.items(), 1):
        print_function_header(name, processor)

        async with processor:
            processor.set_processor(name, cfg)

            await processor.run_pre()
            await processor
            if name != next(reversed(config)):  # only run post up to penultimate function
                await processor.run_post()

            processor.logger.print_line()


def close(processor: MusifyProcessor) -> None:
    """Close the ``processor`` and log closing messages."""
    print_header()
    processor.logger.debug(f"Time taken: {processor.time_taken}")
    logging.shutdown()

    print_folders(processor)
    print_time(processor.time_taken)
    print()


if __name__ == "__main__":
    print_header()
    config_base, config_functions = setup()

    main_processor = MusifyProcessor(config=config_base)
    print_sub_header(main_processor)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(lambda lp, context: lp.stop())

    task = loop.create_task(main(main_processor, config_functions))
    try:
        loop.run_until_complete(task)
    except (Exception, KeyboardInterrupt):
        main_processor.logger.debug(traceback.format_exc())
        print(f"\33[91m{traceback.format_exc(0)}\33m")
        sys.exit(1)
    finally:
        close(main_processor)
