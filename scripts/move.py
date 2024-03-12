# Remap paths in library files & playlists after restructuring files
import json
import logging
import os
import shutil
from collections.abc import Iterable
from os.path import basename, dirname, join, splitext

from musify.local.library import LocalLibrary
from musify.local.library.musicbee import XMLLibraryParser, MusicBee
from musify.shared.logger import STAT, MusifyLogger
from musify.spotify.processors.wrangle import SpotifyDataWrangler

logging.basicConfig(format="%(message)s", level=STAT)


def jprint(data) -> None:
    print(json.dumps(data, indent=2))


def get_mapping(actual: LocalLibrary, reference: LocalLibrary) -> dict[str, str]:
    return {
        next(
            tr for tr in actual if (
                    (track.has_uri and tr.uri == track.uri)
                    or (not track.has_uri and tr.filename == track.filename and tr.length == track.length)
            )
        ).path: track.path
        for track in reference
    }


def check_mapping(data: dict[str, str], fail: bool = True) -> None:
    # noinspection SpellCheckingInspection
    ignore_albums = [
        "Ministry of Sound ONE",
        "Ministry of Sound Anthems",
        "Trance Nation - The Collection",
        "My Generation - The Very Best of the Who",
    ]
    # noinspection SpellCheckingInspection
    ignore_filenames = [
        "Resurection.flac",
        "Miserlou.flac",
    ]

    bad_map = {}
    for old, new in data.items():
        if splitext(basename(old))[0] == splitext(basename(new))[0]:
            continue
        elif any(basename(dirname(old)) == album for album in ignore_albums):
            continue
        elif any(basename(old) == filename for filename in ignore_filenames):
            continue
        bad_map[old] = new

    if bad_map:
        print("Bad mapping found")
        jprint(bad_map)

        if fail:
            raise LookupError("Bad mapping found")


def remap_library(paths: dict[str, str], library_folder: str, staging_folder: str, logger: MusifyLogger) -> None:
    """Replace library file paths"""
    paths = {
        XMLLibraryParser.to_xml_path(old):
            XMLLibraryParser.to_xml_path(new.replace(staging_folder, library_folder))
        for old, new in paths.items()
    }
    # jprint(path_map_xml)

    path_lib_file = join(library_folder, "MusicBee", MusicBee.xml_library_filename)
    with open(path_lib_file, "r", encoding="utf-8") as file:
        library_data = file.read()

    for old, new in logger.get_progress_bar(paths.items(), desc="Remapping library file", unit="paths"):
        if old not in library_data:
            raise FileNotFoundError(f"Could not find old path: {old}")

        library_data_replaced = library_data.replace(old, new)
        assert library_data_replaced != library_data
        library_data = library_data_replaced

    with open(path_lib_file, "w", encoding="utf-8") as file:
        file.write(library_data)


def remap_playlists(
        paths: dict[str, str],
        library_folder: str,
        staging_folder: str,
        playlist_paths: Iterable[str],
        logger: MusifyLogger
) -> None:
    """Replace playlist paths"""
    paths = {
        old.replace(library_folder, ""): new.replace(staging_folder, "").replace("&", "&amp;")
        for old, new in paths.items()
    }
    # jprint(path_map_stem)

    for playlist_path in logger.get_progress_bar(playlist_paths, desc="Remapping playlists", unit="playlists"):
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
        remapping[old] = join(dirname(old), basename(new))
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
    lib.load_tracks()

    # downloads = LocalLibrary("D:\\Music - Downloads", remote_wrangler=remote_wrangler)
    # downloads.load_tracks()
    #
    # remap_all(lib, flac)

    flac = LocalLibrary("I:\\Music", remote_wrangler=remote_wrangler)
    flac.load_tracks()

    replace_files(lib, flac)
