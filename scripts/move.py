# Remap paths in library files & playlists after restructuring files
import asyncio
import json
import logging
import os
import shutil
from collections.abc import Iterable
from pathlib import Path

from musify.libraries.local.library import LocalLibrary
from musify.libraries.local.library.musicbee import XMLLibraryParser, MusicBee
from musify.logger import MusifyLogger, STAT
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler

logging.basicConfig(format="%(message)s", level=STAT)


def jprint(data) -> None:
    print(json.dumps(data, indent=2))


def get_mapping(actual: LocalLibrary, reference: LocalLibrary) -> dict[Path, Path]:
    return {
        next(
            tr for tr in actual if (
                    (track.has_uri and tr.uri == track.uri)
                    or (not track.has_uri and tr.filename == track.filename and tr.length == track.length)
            )
        ).path: track.path
        for track in reference
    }


def check_mapping(data: dict[Path, Path], fail: bool = True) -> None:
    # noinspection SpellCheckingInspection
    ignore_albums = [
    ]
    # noinspection SpellCheckingInspection
    ignore_filenames = [
    ]

    bad_map = {}
    for old, new in data.items():
        if old.stem == new.stem:
            continue
        elif any(old.parent.name == album for album in ignore_albums):
            continue
        elif any(old.name == filename for filename in ignore_filenames):
            continue
        bad_map[old] = new

    if bad_map:
        print("Bad mapping found")
        jprint(bad_map)

        if fail:
            raise LookupError("Bad mapping found")


def remap_library(paths: dict[Path, Path], library_folder: Path, staging_folder: Path, logger: MusifyLogger) -> None:
    """Replace library file paths"""
    paths = {
        XMLLibraryParser.to_xml_path(old):
            XMLLibraryParser.to_xml_path(str(new).replace(str(staging_folder), str(library_folder)))
        for old, new in paths.items()
    }
    # jprint(path_map_xml)

    path_lib_file = library_folder.joinpath("MusicBee", MusicBee.xml_library_path)
    with open(path_lib_file, "r", encoding="utf-8") as file:
        library_data = file.read()

    for old, new in logger.get_synchronous_iterator(paths.items(), desc="Remapping library file", unit="paths"):
        if old not in library_data:
            raise FileNotFoundError(f"Could not find old path: {old}")

        library_data_replaced = library_data.replace(old, new)
        assert library_data_replaced != library_data
        library_data = library_data_replaced

    with open(path_lib_file, "w", encoding="utf-8") as file:
        file.write(library_data)


def remap_playlists(
        paths: dict[Path, Path],
        library_folder: Path,
        staging_folder: Path,
        playlist_paths: Iterable[Path],
        logger: MusifyLogger
) -> None:
    """Replace playlist paths"""
    paths = {
        str(old).replace(str(library_folder), ""):
            str(new).replace(str(staging_folder), "").replace("&", "&amp;")
        for old, new in paths.items()
    }
    # jprint(path_map_stem)

    for playlist_path in logger.get_synchronous_iterator(playlist_paths, desc="Remapping playlists", unit="playlists"):
        with open(playlist_path, "r", encoding="utf-8") as file:
            playlist = file.read()

        for old, new in paths.items():
            playlist = playlist.replace(old, new)

        with open(playlist_path, "w", encoding="utf-8") as file:
            file.write(playlist)


def remap_all(library: LocalLibrary, staging: LocalLibrary):
    mapping = get_mapping(library, flac)
    # jprint(mapping)
    check_mapping(mapping)

    remap_library(
        paths=mapping,
        library_folder=library.library_folders[0],
        staging_folder=staging.library_folders[0],
        logger=library.logger,
    )
    remap_playlists(
        paths=mapping,
        library_folder=library.library_folders[0],
        staging_folder=staging.library_folders[0],
        playlist_paths=library._playlist_paths.values(),
        logger=library.logger,
    )


def replace_files(library: LocalLibrary, staging: LocalLibrary) -> None:
    mapping = get_mapping(library, staging)
    # jprint(mapping)
    check_mapping(mapping, fail=False)

    remapping = {}
    for old, new in mapping.items():
        remapping[old] = old.joinpath(new.name)
        shutil.copyfile(new, remapping[old])
        os.remove(old)

    remap_library(
        paths=remapping,
        library_folder=library.library_folders[0],
        staging_folder=library.library_folders[0],
        logger=library.logger,
    )
    remap_playlists(
        paths=remapping,
        library_folder=library.library_folders[0],
        staging_folder=library.library_folders[0],
        playlist_paths=library._playlist_paths.values(),
        logger=library.logger,
    )


if __name__ == "__main__":
    remote_wrangler = SpotifyDataWrangler()

    lib = MusicBee("M:\\Music\\MusicBee", remote_wrangler=remote_wrangler)
    asyncio.run(lib.load_tracks())

    # downloads = LocalLibrary("D:\\Music - Downloads", remote_wrangler=remote_wrangler)
    # downloads.load_tracks()
    #
    # remap_all(lib, flac)

    flac = LocalLibrary("I:\\Music", remote_wrangler=remote_wrangler)
    asyncio.run(flac.load_tracks())

    replace_files(lib, flac)
