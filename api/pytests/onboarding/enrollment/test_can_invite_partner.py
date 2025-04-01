from unittest import mock

from models import tracks
from models.tracks import TrackName
from pytests import factories


def test_get_can_invite_partner(client, api_helpers, verification):
    # Given
    user = factories.MemberFactory.create()
    factories.UserOrganizationEmployeeFactory.create(
        organization_employee__organization__allowed_tracks=[*tracks.TrackName],
        user=user,
    )
    factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.PARENTING_AND_PEDIATRICS,
    )
    given_url = f"/api/v1/users/{user.id}/invite_partner_enabled"
    expected_status_code = 200
    expected_body = {"can_invite_partner": True}
    other_user_ids_in_family = [456, 789]

    # When
    with mock.patch(
        "eligibility.verify_members",
        return_value=[verification],
    ), mock.patch(
        "eligibility.EnterpriseVerificationService.get_other_user_ids_in_family",
        return_value=other_user_ids_in_family,
    ):
        res = client.get(
            given_url,
            headers=api_helpers.json_headers(user),
        )
    # Then
    assert res.status_code == expected_status_code
    assert res.json == expected_body
