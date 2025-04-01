import json
import pathlib
from unittest import mock

import pytest

from data_admin.factory import create_data_admin_app
from pytests.factories import RoleFactory, StateFactory


@pytest.fixture(scope="package")
def data_admin_app():
    with mock.patch(
        "data_admin.common.safe_get_project_id", return_value="gitlab-saas"
    ):
        app = create_data_admin_app()
        app.testing = True
        app.env = "testing"
        return app


@pytest.fixture
def load_fixture():
    def load_fixture_from_file(filename):
        file_location = "/" + str(
            pathlib.Path(__file__).parent.parent / "fixtures" / filename
        )
        with open(file_location, "r") as file:
            raw_fixture = file.read()
            json_fixture = json.loads(raw_fixture)
        return json_fixture

    return load_fixture_from_file


@pytest.fixture(scope="function")
def mock_enterprise_verification_service():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch(
        "eligibility.EnterpriseVerificationService", autospec=True
    ) as mock_service, mock.patch(
        "data_admin.makers.user.e9y_service.get_verification_service", autospec=True
    ) as mock_get_service_data_admin, mock.patch(
        "tracks.service.tracks.get_verification_service", autospec=True
    ) as mock_get_service_tracks, mock.patch(
        "eligibility.get_verification_service", autospec=True
    ) as mock_get_service:
        mock_get_service_data_admin.return_value = mock_service
        mock_get_service_tracks.return_value = mock_service
        mock_get_service.return_value = mock_service
        yield mock_service


@pytest.fixture(scope="function")
def user_dependencies():
    RoleFactory.create()
    StateFactory.create()
