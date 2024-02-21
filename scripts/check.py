# Check the differences in paths between equal playlists from different sources
import json
import re
from glob import glob
from os.path import join, splitext, basename

playlists_src = "D:\\Music\\MusicBee\\ExportedPlaylists"
playlists_trg = "D:\\___Playlists"

playlist_names = [splitext(basename(path))[0] for path in glob(join(f"{playlists_src}", "*.m3u"))]


def clean_path(path: str) -> str:
    path = re.sub(r"^\.\./", "", path)
    path = re.sub(r"D:\\Music", "", path)
    name = splitext(basename(path.replace("/", "\\")).rstrip())[0]
    return re.sub(r"^\d{2} - ", "", name).rstrip().casefold()


def jprint(data) -> None:
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    for name in playlist_names:
        with open(join(playlists_src, name + ".m3u"), "r") as file:
            src_paths: set[str] = {clean_path(line) for line in file if line}
        with open(join(playlists_trg, name + ".m3u"), "r") as file:
            trg_paths: set[str] = {clean_path(line) for line in file if line}

        print(name)
        jprint(list(src_paths.difference(trg_paths)))
