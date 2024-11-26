import pytest

from musify_cli.parser.library.remote import RemoteLibraryConfig, APIConfig, SpotifyAPIConfig


class TestRemoteLibrary:
    @pytest.fixture
    def api_model(self) -> APIConfig:
        return SpotifyAPIConfig(
            client_id="",
            client_secret="",
        )

    def test_assigns_type_from_api_model(self, api_model: APIConfig):
        model = RemoteLibraryConfig(name="name", api=api_model)
        assert model.type == api_model.source
