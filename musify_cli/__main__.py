import argparse
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta

from .config import Config
from .main import Musify
from .printers import print_logo, print_line, print_time
from musify import PROGRAM_NAME


# noinspection PyProtectedMember
def get_parser() -> argparse.ArgumentParser:
    """Get the terminal input parser"""
    parser = argparse.ArgumentParser(
        description="Sync your local library to remote libraries and other useful functions.",
        prog=PROGRAM_NAME,
        usage="%(prog)s [options] [function]"
    )
    parser._positionals.title = "Functions"
    parser._optionals.title = "Optional arguments"

    # cli function aliases and expected args in order user should give them
    parser.add_argument(
        "functions", nargs="*", choices=list(Musify.__new__(Musify).__processormethods__),
        help=f"{PROGRAM_NAME} function to run."
    )

    runtime = parser.add_argument_group("Runtime options")
    runtime.add_argument(
        "-c", "--config", type=str, required=False, nargs="?", dest="config_path",
        default="config.yml",
        help="The path to the config file to use"
    )
    runtime.add_argument(
        "-k", "--config-key", type=str, required=False, nargs="?", dest="config_key",
        default="general",
        help="The key for the initial config."
    )
    runtime.add_argument(
        "-lc", "--log-config", type=str, required=False, nargs="?", dest="log_config_path",
        default="logging.yml",
        help="The path to the logging config file to use"
    )
    runtime.add_argument(
        "-ln", "--log-name", type=str, required=False, nargs="?", dest="log_name",
        help="The logger settings to use for this run as can be found in logging config file"
    )
    runtime.add_argument(
        "-x", "--execute", action="store_false", dest="dry_run",
        help="Modify user's local and remote files and playlists. Otherwise, do not affect files."
    )

    libraries = parser.add_argument_group("Library options")
    libraries.add_argument(
        "-l", "--local", type=str, required=True, nargs="?", dest="local",
        help="The name of the local library to use as can be found in the config file"
    )
    libraries.add_argument(
        "-r", "--remote", type=str, required=True, nargs="?", dest="remote",
        help="The name of the remote library to use as can be found in the config file"
    )

    functions = parser.add_argument_group("Function options")
    functions.add_argument(
        "-bk", "--backup-key", type=str, required=False, nargs="?", dest="backup_key",
        default=None,
        help="When running backup operations, the key to give to backups"
    )
    functions.add_argument(
        "-nmn", "--new-music-name", type=str, required=False, nargs="?", dest="new_music_name",
        default="New Music",
        help="When running new_music operations, the name to give to the new music playlist"
    )
    functions.add_argument(
        "-nms", "--new-music-start", required=False, nargs="?", dest="new_music_start",
        type=lambda x: datetime.strptime(x, "%Y-%m-%d"), default=datetime.now() - timedelta(weeks=4),
        help="When running new_music operations, the earliest date to get new music for"
    )
    functions.add_argument(
        "-nme", "--new-music-end", required=False, nargs="?", dest="new_music_end",
        type=lambda x: datetime.strptime(x, "%Y-%m-%d"), default=datetime.now(),
        help="When running new_music operations, the latest date to get new music for"
    )

    return parser


print()
print_logo()
named_args = get_parser().parse_known_args()[0]

conf = Config(named_args.config_path)
conf.load_log_config(named_args.log_config_path, named_args.log_name, __name__)
conf.load(named_args.config_key)
conf.dry_run = named_args.dry_run

main = Musify(config=conf, local=named_args.local, remote=named_args.remote)

# log header
if main.logger.file_paths:
    main.logger.info(f"\33[90mLogs: {", ".join(main.logger.file_paths)} \33[0m")
main.logger.info(f"\33[90mOutput: {conf.output_folder} \33[0m")
main.logger.print()
if conf.dry_run:
    print_line("DRY RUN ENABLED", " ")

main.api.authorise()
for i, func in enumerate(named_args.functions, 1):
    title = f"{PROGRAM_NAME}: {func}"
    if conf.dry_run:
        title += " (DRYRUN)"

    if sys.platform == "win32":
        os.system(f"title {title}")
    elif sys.platform == "linux" or sys.platform == "darwin":
        os.system(f"echo '\033]2;{title}\007'")

    try:  # run the functions requested by the user
        print_line(func)
        # initialise the libraries
        assert main.local.library is not None
        assert main.remote.library is not None

        method = main.set_processor(func)
        main(
            key=named_args.backup_key,
            name=named_args.new_music_name,
            start=named_args.new_music_start,
            end=named_args.new_music_end,
        )
    except (Exception, KeyboardInterrupt):
        main.logger.critical(traceback.format_exc())
        break

main.logger.debug(f"Time taken: {main.time_taken}")
logging.shutdown()
print_logo()
print_time(main.time_taken)
