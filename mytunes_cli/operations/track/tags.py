from collections.abc import Iterator, MutableMapping, Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, Self

import yaml
from mytunes.core.api import BatchReadEndpoints, ItemsReadEndpoints
from mytunes.core.api.items import HasTrackEndpoints
from mytunes.core.sequence import MutableUniqueSequence, UniqueSequence
from mytunes.core.track import RemoteTrack
from mytunes.exception import APIError
from mytunes.local.track import LocalTrack
from mytunes.processors.tagger import Tagger, TaggerResult
from pydantic import Field, model_validator, PrivateAttr, FilePath
from pydantic.alias_generators import to_snake
from pydantic_settings import CliPositionalArg, CliSuppress

from mytunes_cli.operations._base import RemoteToLocalOperation, LocalLibraryOperation, TagOperation


class PullTags(RemoteToLocalOperation, TagOperation):
    _tracks: MutableUniqueSequence[RemoteTrack] = PrivateAttr(
        default_factory=MutableUniqueSequence,
    )

    @property
    def tracks(self) -> Iterator[RemoteTrack]:
        self._tracks.extend(self.source.tracks)
        self._tracks.extend(track for playlist in self.source.playlists for track in playlist.tracks)
        self._tracks.extend(track for album in self.source.albums for track in album.tracks)
        self._tracks.extend(
            track for artist in self.source.artists for album in artist.albums for track in album.tracks
        )
        return self._tracks.unique

    async def load(self):
        log_state = not self.state.get_load_state(self.target.load_tracks)
        await self.target.load_tracks()

        if log_state:
            self.target.log_tracks()

        await self.source.load_tracks()
        await self.source.load_playlists()
        await self.source.load_playlist_items()

        uris_loaded = {track.uri for track in self.tracks}
        uris_to_load = {
            track.uri for track in self.target.tracks if track.has_uri and track.uri not in uris_loaded
        }

        api = HasTrackEndpoints.validate_api(self.source.api)
        for endpoint in (ItemsReadEndpoints, BatchReadEndpoints):
            with suppress(APIError):
                api = endpoint.validate_api(api)
                break
        else:
            raise APIError(f"Cannot run {self.operation_name!r}: API does not support loading tracks")

        self._tracks.extend(await api.get_many(tuple(uris_to_load), limit=self.source.concurrency))

    async def run(self) -> None:
        self.target.merge_tracks(self.tracks, include=self.include, exclude=self.exclude, replace=self.replace)
        await self._save_tracks(self.target)

    def _log_start(self) -> None:
        message = (
            f"Pulling tags for {self.target.track_total} tracks from {self.source.source.title()} library "
            f"to {self.target.source.title()} library"
        )
        self._logger.info(message, header=1, new_line_start=True)


class RuleTags(LocalLibraryOperation, TagOperation):
    rules: CliPositionalArg[FilePath | list[Tagger]] = Field(
        description="The path to the rules to use for applying tags to tracks.",
        alias="rules_path",
    )
    rules_for_unmatched: CliSuppress[Tagger | None] = Field(
        description="The rule set that will be applied to all unmatched tracks.",
        alias="unmatched",
        default=None,
    )

    @model_validator(mode="before")
    @classmethod
    def _extract_unmatched_rules[T](cls, data: T | MutableMapping[str, Any]) -> Self:
        rules = cls._get_value_from_data(data, "rules")
        if rules is None or not isinstance(rules, list) or not all(isinstance(it, Mapping) for it in rules):
            return data

        # handle tagger for unmatched items
        for idx, rule_set in enumerate(rules):
            item_filter = Tagger._get_value_from_data(rule_set, filter_key := "filter")
            if not isinstance(item_filter, str) or item_filter != "UNMATCHED":
                continue

            for alias in Tagger._get_aliases(filter_key):
                rule_set.pop(alias, None)

            data[to_snake(item_filter)] = rule_set
            del rules[idx]
            break

        return data

    @model_validator(mode="before")
    @classmethod
    def _load_rules[T](cls, data: T | MutableMapping[str, Any]) -> Self:
        if not isinstance(data, MutableMapping):
            return data

        path = cls._get_value_from_data(data, rules_key := "rules")
        if path is None:
            return data

        if isinstance(path, list) and len(path) == 1 and isinstance(path[0], str | Path):
            path = path[0]
        if not isinstance(path, str | Path):
            return data

        with Path(path).open("r", encoding="utf-8") as file:
            rules = yaml.safe_load(file.read())

        if isinstance(rules, Mapping) and rules_key in rules:
            rules = rules[rules_key]

        for alias in cls._get_aliases(rules_key):
            data.pop(alias, None)
        data[rules_key] = rules

        return data

    async def load(self):
        log_state = not self.state.get_load_state(self.library.load_tracks)
        await self.library.load_tracks()

        if log_state:
            self.library.log_tracks()

    async def run(self) -> None:
        results = self._get_results()
        if self.rules_for_unmatched is not None:
            unmatched_results = self._get_unmatched_results(results)
            results.extend(unmatched_results)

        results = [result for result in results if result.tags]
        if not results:
            self._logger.info("[blue]No tags updated.[/]")
            return

        next(iter(self.rules)).log_results(results)

        await self._save_tracks(self.library, tracks=[result.item for result in results])

    def _log_start(self) -> None:
        message = (
            f"Applying {len(self.rules)} tag rules to {self.library.track_total} tracks "
            f"in {self.source} library"
        )
        self._logger.info(message, header=1, new_line_start=True)

    def _get_results(self) -> list[TaggerResult[LocalTrack]]:
        results: list[TaggerResult] = []
        for rule_set in self.rules:
            rule_results = rule_set.set_tags_to_items(self.library.tracks)
            results.extend(rule_results)

        return results

    def _get_unmatched_results(self, results: list[TaggerResult[LocalTrack]]) -> tuple[TaggerResult[LocalTrack], ...]:
        unmatched = self.library.tracks.difference(UniqueSequence(result.item for result in results))
        return self.rules_for_unmatched.set_tags_to_items(unmatched)
