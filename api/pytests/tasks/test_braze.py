from unittest import mock

import pytest

from models.tracks import TrackName
from tasks.braze import report_last_eligible_through_organization, send_password_setup


@pytest.fixture
def patch_track_user():
    with mock.patch("utils.braze.track_user") as track_user:
        yield track_user


@pytest.fixture
def patch_new_user_password_set():
    with mock.patch(
        "utils.braze_events.new_user_password_set"
    ) as new_user_password_set:
        yield new_user_password_set


@pytest.fixture
def patch_send_last_eligible_through_organization():
    with mock.patch(
        "utils.braze.send_last_eligible_through_organization"
    ) as send_last_eligible_through_organization:
        yield send_last_eligible_through_organization


def test_send_password_setup(factories, patch_track_user, patch_new_user_password_set):
    # Arrange
    esp_id = "esp_id"

    user = factories.DefaultUserFactory.create(esp_id=esp_id)

    # Act
    send_password_setup(user.id)

    # Assert
    patch_track_user.assert_called_with(user)
    patch_new_user_password_set.assert_called_with(user)


def test_report_last_eligible_through_organization(
    factories, patch_send_last_eligible_through_organization
):
    esp_id = "esp_id"
    organization_name = "ACME"
    organization = factories.OrganizationFactory(name=organization_name)

    user = factories.EnterpriseUserNoTracksFactory.create(esp_id=esp_id)
    factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
        user=user,
        client_track=factories.ClientTrackFactory(organization=organization),
    )

    report_last_eligible_through_organization(user.id)

    patch_send_last_eligible_through_organization.assert_called_with(
        esp_id,
        organization_name,
    )


def test_report_last_eligible_through_organization_when_user_not_found(
    patch_send_last_eligible_through_organization,
):
    report_last_eligible_through_organization(123123123)

    patch_send_last_eligible_through_organization.assert_not_called()


def test_report_last_eligible_through_organization_when_organization_not_found(
    factories, patch_send_last_eligible_through_organization
):
    report_last_eligible_through_organization(factories.DefaultUserFactory.create().id)

    patch_send_last_eligible_through_organization.assert_not_called()
