"""
The core parser sets up and configures the parser for all possible arguments accepted by the program.
"""
import os
from copy import deepcopy
from datetime import date, timedelta, datetime
from functools import partial
from pathlib import Path
from typing import Any

import yaml
from jsonargparse import ArgumentParser, ActionParser, Namespace
from musify import PROGRAM_NAME
from musify.field import TagFields
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.download import ItemDownloadHelper
from musify.processors.filter import FilterComparers
from musify.report import report_missing_tags
from musify.utils import merge_maps

from musify_cli import PACKAGE_ROOT
from musify_cli.parser._library import LIBRARY_EPILOG, LOCAL_LIBRARY_TYPES, REMOTE_LIBRARY_TYPES, LIBRARY_PARSER
from musify_cli.parser._setup import setup
from musify_cli.parser._utils import EpilogHelpFormatter, LOCAL_TRACK_TAG_NAMES
from musify_cli.parser._utils import LoadTypesLocal, LoadTypesRemote, EnrichTypesRemote
from musify_cli.parser._utils import get_default_args, get_tags, get_comparers_filter
from musify_cli.exception import ParserError

setup()

CORE_PARSER = ArgumentParser(
    prog=PROGRAM_NAME,
    description="Manage your local library and remote libraries programmatically.",
    formatter_class=EpilogHelpFormatter,
    epilog="==FORMATTED==" + LIBRARY_EPILOG
)
# noinspection PyProtectedMember
CORE_PARSER._optionals.title = "Help and external config"


###########################################################################
## Link argument helpers
###########################################################################
def append_parent_folder(path: str | Path, parent_folder: str | Path | os.PathLike) -> Path:
    """When the given ``path`` is relative, append the ``parent_folder`` as the parent directory"""
    if Path(path).is_absolute():
        return path
    return Path(parent_folder).joinpath(path)


###########################################################################
## Runtime
###########################################################################
runtime_group = CORE_PARSER.add_argument_group(
    title="Runtime options",
    description="Runtime functionality of the program e.g. app data output, logging etc."
)
runtime_group.add_argument(
    "-x", "--execute", action="store_true",
    help="Run all write operations i.e. modify actual data on any write/save/sync commands"
)

logging_parser = ArgumentParser(prog="Logging", formatter_class=EpilogHelpFormatter)
logging_parser.add_argument(
    "--config-path", type=Path,
    help="The path to the logging config file to use."
)
logging_parser.add_argument(
    "--name", type=str,
    help="The logger settings to use for this run as found in logging config file."
)
runtime_group.add_argument("--logging", action=ActionParser(logging_parser))

app_data_group = CORE_PARSER.add_argument_group(
    title="App data directories",
    description="Control the hierarchy of files needed and/or exported by the program "
                "e.g. backups, API tokens, caches etc."
)
app_data = ArgumentParser(prog="App data", formatter_class=EpilogHelpFormatter)
app_data.add_argument(
    "--base", type=Path, default=PACKAGE_ROOT.joinpath("_data"),
    help="The base directory to use for output data e.g. backups, API tokens, caches etc."
)
app_data.add_argument(
    "--backup", type=Path, default="backup",
    help="The directory to use for backup output. May either be a full path or relative path to the '--base'"
)
app_data.add_argument(
    "--cache", type=Path, default="cache",
    help="The directory to use for cache output. May either be a full path or relative path to the '--base'"
)
app_data.add_argument(
    "--token", type=Path, default="token",
    help="The directory to use for token files. May either be a full path or relative path to the '--base'"
)
app_data.add_argument(
    "--local-library", type=Path, default=Path("library", "local"),
    help="The directory to use for local library export data. "
         "May either be a full path or relative path to the '--base'"
)

app_data_group.add_argument("--paths", action=ActionParser(app_data))

###########################################################################
## Pre-/Post- operations
###########################################################################
prepost_group = CORE_PARSER.add_argument_group(
    title="Pre-/Post- processing options",
    description="Generic pre-/post- operations of the program e.g. reload, pauses, filtering etc."
)
prepost_group.add_argument(
    "--filter", type=get_comparers_filter, default=FilterComparers(),
    help="A generic filter to apply for the current operation. Only used during specific operations."
)
prepost_group.add_argument(
    "--pause", type=str,
    help="When provided, pause the operation after this function is complete "
         "and display the given value as a message in the CLI."
)

reload_group = prepost_group.add_argument_group(
    title="Reload libraries options",
    description="Options for reloading various items/collections in the loaded libraries"
)
reload = ArgumentParser(prog="Reload", formatter_class=EpilogHelpFormatter)

reload.add_argument(
    "--local.types", type=list[LoadTypesLocal],
    help="The types of items/collections to reload for the local library. "
         f"Accepted types: {[enum.name.lower() for enum in LoadTypesRemote.all()]}"
)
reload.add_argument(
    "--remote.types", type=list[LoadTypesRemote],
    help="The types of items/collections to reload for the remote library. "
         f"Accepted types: {[enum.name.lower() for enum in LoadTypesRemote.all()]}"
)
reload.add_argument(
    "--remote.extend", type=bool,
    help="Extend the remote library with items in the matched items local library"
)
reload.add_argument(
    "--remote.enrich.enabled", type=bool,
    help="Enrich the loaded items/collections in this library"
)
reload.add_argument(
    "--remote.enrich.types", type=list[EnrichTypesRemote],
    help="The types of sub items/collections to enrich for the remote library. "
         f"Accepted types: {[enum.name.lower() for enum in EnrichTypesRemote.all()]}"
)

reload_group.add_argument("--reload", action=ActionParser(reload))

###########################################################################
## Backup/Restore
###########################################################################
backup_group = CORE_PARSER.add_argument_group(title="Backup/restore options")
backup_group.add_argument(
    "--backup.key", type=str,
    help="The key to give to backups"
)

###########################################################################
## Reports
###########################################################################
reports_group = CORE_PARSER.add_argument_group(
    title="Reports options",
    description="Options for all reporting operations"
)
reports = ArgumentParser(prog="Reports", formatter_class=EpilogHelpFormatter)

reports_base = ArgumentParser(formatter_class=EpilogHelpFormatter)
reports_base.add_argument(
    "--enabled", type=bool, default=False,
    help="When true, trigger this report."
)
reports_base.add_argument(
    "--filter", type=get_comparers_filter, default=FilterComparers(),
    help="A filter to apply for this report."
)

reports_playlist_differences = deepcopy(reports_base)
reports_playlist_differences.prog = "Report - Playlist Differences"
reports.add_argument(
    "--playlist_differences", action=ActionParser(reports_playlist_differences)
)

reports_missing_tags = deepcopy(reports_base)
reports_missing_tags.prog = "Report - Missing Tags"
reports_missing_tags_default_args = get_default_args(report_missing_tags)
reports_missing_tags.add_argument(
    "--tags", type=get_tags, default=reports_missing_tags_default_args.get("tags", LocalTrackField.ALL),
    help=f"The tags to check. Accepted tags: {LOCAL_TRACK_TAG_NAMES}"
)
reports_missing_tags.add_argument(
    "--match-all", type=bool, default=reports_missing_tags_default_args.get("match_all", False),
    help="When True, consider a track as having missing tags only if it is missing all the given tags."
)
reports.add_argument(
    "--missing_tags", action=ActionParser(reports_missing_tags)
)

reports_group.add_argument("--reports", action=ActionParser(reports))

###########################################################################
## Item Download Helper
###########################################################################
downloader_group = CORE_PARSER.add_argument_group(
    title="Downloader options",
    description=f"Options for {ItemDownloadHelper.__name__} operations"
)
remote_downloader = ArgumentParser(prog="Remote item download", formatter_class=EpilogHelpFormatter)

remote_downloader.add_class_arguments(ItemDownloadHelper, as_group=False, skip={"fields"})
# WORKAROUND: this should be assigned in the add_class_arguments step
#  Currently, it is not being assigned there for some unknown reason
remote_downloader.add_argument(
    "--urls", type=list[str], default=get_default_args(ItemDownloadHelper).get("urls"),
    help="The template URLs for websites to open queries for. "
         "The given sites should contain exactly 1 '{}' placeholder into which the processor can place "
         "a query for the item being searched. e.g. *bandcamp.com/search?q={}&item_type=t*"
)
remote_downloader.add_argument(
    "--fields", type=partial(get_tags, cls=TagFields), default=get_default_args(ItemDownloadHelper).get("fields"),
    help=f"The tags to use when searching for items. Accepted tags: {LOCAL_TRACK_TAG_NAMES}"
)

downloader_group.add_argument("--download", action=ActionParser(remote_downloader))


###########################################################################
## New Music
###########################################################################
new_music_group = CORE_PARSER.add_argument_group(
    title="New music playlist generator options",
    description="Options for generating a playlist for new music in a remote library",
)
new_music = ArgumentParser(prog="New music playlist generator", formatter_class=EpilogHelpFormatter)

new_music.add_argument(
    "--name", type=str, default="New Music",
    help="The name to give to the new music playlist. When the given playlist name already exists, "
         "update the tracks in the playlist instead of generating a new one.",
)
new_music.add_argument(
    "--start", type=date, default=(datetime.now() - timedelta(weeks=4)).date(),
    help="The earliest date to get new music for."
)
new_music.add_argument(
    "--end", type=date, default=datetime.now().date(),
    help="The latest date to get new music for."
)

new_music_group.add_argument("--new-music", action=ActionParser(new_music))


###########################################################################
## Libraries
###########################################################################
libraries_group = CORE_PARSER.add_argument_group(
    title="Libraries options",
    description="Set options for local and remote libraries here"
)
libraries = ArgumentParser(prog="Libraries", formatter_class=EpilogHelpFormatter)

libraries.add_argument(
    "--config-path", type=Path | None,
    help="The file path of the libraries"
)
libraries.add_argument(
    "-l", "--local", type=str | dict | Namespace, required=True,
    help="The name of the local library to use as can be found in the library config OR "
         "the library config for the local library. "
         f"Config must be of one of the following types: {LOCAL_LIBRARY_TYPES}",
)
libraries.add_argument(
    "-r", "--remote", type=str | dict | Namespace, required=True,
    help="The name of the remote library to use as can be found in the library config OR "
         "the library config for the remote library. "
         f"Config must be of one of the following types: {REMOTE_LIBRARY_TYPES}",
)

libraries_group.add_argument("--libraries", action=ActionParser(libraries))


def load_library_config(
        lib: str | dict, config_path: Path | None = None, overwrite: str | dict = None
) -> dict[str, Any]:
    """
    Process the given library config ``lib`` at the ``config_path``.
    Overwrite loaded config with ``overwrite``.
    """
    if isinstance(overwrite, str):
        lib = overwrite
        overwrite = None

    if isinstance(lib, str):
        if config_path is None:
            raise ParserError("Library name given but no config path given. Provide a path to the library config file.")

        with open(config_path, "r", encoding="utf-8") as file:
            config = yaml.full_load(file)

        name = lib
        if not config.get(name):
            raise ParserError(f"Library name not found: {name!r}. Available libraries: {list(config.keys())}")

        lib = {"name": name} | config[name]

    if overwrite:
        merge_maps(lib, overwrite, extend=False, overwrite=True)

    return lib


def parse_library_config(
        lib: str | dict, config_path: Path | None = None, overwrite: dict[str, Any] = None
) -> Namespace:
    """
    Process the given local library config ``lib`` at the ``config_path``.
    Overwrite loaded config with ``overwrite``.
    """
    data = load_library_config(lib=lib, config_path=config_path, overwrite=overwrite)
    return LIBRARY_PARSER.parse_object(data)


CORE_PARSER.link_arguments(
    ("libraries.local", "libraries.config_path"),
    "libraries.local",
    parse_library_config
)
CORE_PARSER.link_arguments(
    ("libraries.remote", "libraries.config_path"),
    "libraries.remote",
    parse_library_config
)
