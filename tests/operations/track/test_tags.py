from copy import deepcopy
from unittest.mock import Mock

import pytest
from faker import Faker
from mytunes.core.library import RemoteMutableLibrary
from mytunes.core.track import RemoteTrack
from mytunes.local.track import LocalTrack
from mytunes.processors.filters import ValueFilter
from mytunes.processors.tagger import Tagger, TaggerResult, ValueSetter
from mytunes.processors.tagger.values import FixedValue
from pytest_mock import MockerFixture

from mytunes_cli.operations._base import TAGS_SAVE
from mytunes_cli.operations.track.tags import PullTags, RuleTags
from mytunes_cli.state import GlobalState
from operations.testers import OperationTester
from utils import split_list


class TestPullTags(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState, local_library_name: str, remote_library_name: str, faker: Faker) -> PullTags:
        include = faker.random_elements(TAGS_SAVE, unique=True)
        exclude = faker.random_elements(TAGS_SAVE, unique=True)
        return PullTags(
            state=state,
            source_name=remote_library_name,
            target_name=local_library_name,
            include=include,
            exclude=exclude,
        )

    @pytest.fixture(autouse=True)
    def source_tracks(self, model: PullTags, remote_tracks: list[RemoteTrack]) -> list[RemoteTrack]:
        source = model.source
        assert isinstance(source, RemoteMutableLibrary)
        source.tracks.replace(remote_tracks)
        assert list(model.tracks) == remote_tracks

        return remote_tracks

    @pytest.fixture(autouse=True)
    def target_tracks(self, model: PullTags, local_tracks: list[LocalTrack]) -> list[LocalTrack]:
        model.target.tracks.replace(local_tracks)
        return local_tracks

    async def test_run(self, model: PullTags, mock_save: Mock, mocker: MockerFixture):
        mock_merge = mocker.spy(type(model.target), "merge_tracks")

        await model.run()

        assert mock_merge.call_args.kwargs == dict(
            include=model.include, exclude=model.exclude, replace=model.replace
        )


class TestRuleTags(OperationTester):
    @pytest.fixture
    def model(self, state: GlobalState, local_library_name: str, faker: Faker) -> RuleTags:
        setters = [
            ValueSetter(field="name", value=FixedValue(name=faker.word(), value=faker.name()))
        ]
        tagger = Tagger(setters=setters)

        return RuleTags(state=state, library_name=local_library_name, rules=[tagger])

    @pytest.fixture(autouse=True)
    def tracks(self, model: RuleTags, local_tracks: list[LocalTrack]) -> list[LocalTrack]:
        model.library.tracks.replace(local_tracks)
        return local_tracks

    @pytest.fixture
    def mock_set_tag(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(Tagger, "set_tags_to_items")

    @pytest.fixture
    def mock_unmatched(self, model: RuleTags, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_get_unmatched_results")

    def test_get_results(self, model: RuleTags, mock_set_tag: Mock):
        results = model._get_results()

        assert len(results) == len(model.library.tracks)
        assert [result.item for result in results] == list(model.library.tracks)

        assert mock_set_tag.call_count == len(model.rules)

    def test_get_unmatched_results(self, model: RuleTags, mock_set_tag: Mock):
        model.rules_for_unmatched = deepcopy(next(iter(model.rules)))

        matched, unmatched = split_list(model.library.tracks, 2)
        results = [TaggerResult(item=track) for track in matched]
        results = model._get_unmatched_results(results)

        assert len(results) == len(unmatched)
        assert [result.item for result in results] == unmatched

        mock_set_tag.assert_called_once()

    async def test_run_with_all_matched(
            self, model: RuleTags, mock_save: Mock, mock_set_tag: Mock, mock_unmatched: Mock
    ):
        await model.run()

        # tagger should set all the same names
        assert len(set(track.name for track in model.library.tracks)) == 1

        assert mock_set_tag.call_count == len(model.rules)
        mock_unmatched.assert_not_called()

    async def test_run_with_unmatched(
            self, model: RuleTags, mock_save: Mock, mock_set_tag: Mock, mock_unmatched: Mock
    ):
        model.rules_for_unmatched = deepcopy(next(iter(model.rules)))

        matched, unmatched = split_list(model.library.tracks, 2)
        for rule_set in model.rules:
            rule_set.filter = ValueFilter(values=matched)

        await model.run()

        assert mock_set_tag.call_count == len(model.rules) + 1
        mock_unmatched.assert_called_once()
