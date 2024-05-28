# Check the differences in paths between equal playlists from different sources
import json
import re
from pathlib import Path

playlists_src = Path("M:", "\\" "Music", "MusicBee", "ExportedPlaylists")
playlists_trg = Path("M:", "\\", "___Playlists")

playlist_names = [path.stem for path in playlists_src.glob("*.m3u")]


def clean_path(path: str) -> Path:
    path = re.sub(r"^\.\./", "", str(path))
    path = re.sub(r"M:\\Music", "", path)
    name = Path(path.replace("/", "\\")).stem
    return Path(re.sub(r"^\d{2} - ", "", name))


def jprint(data) -> None:
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    for name in playlist_names:
        with open(playlists_src.joinpath(name + ".m3u"), "r") as file:
            src_paths: set[Path] = {clean_path(line) for line in file if line}
        with open(playlists_trg.joinpath(name + ".m3u"), "r") as file:
            trg_paths: set[Path] = {clean_path(line) for line in file if line}

        print(name)
        jprint(list(src_paths.difference(trg_paths)))
