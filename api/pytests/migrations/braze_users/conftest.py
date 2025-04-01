from datetime import datetime

import pytest

from incentives.models.incentive import IncentiveAction
from models.tracks import TrackName


@pytest.fixture
def fake_enterprise_users(factories):
    user1 = factories.DefaultUserFactory.create(
        esp_id="esp_id1",
        email="fake1@email.com",
    )
    user2 = factories.DefaultUserFactory.create(
        esp_id="esp_id2",
        email="fake2@email.com",
    )
    user3 = factories.DefaultUserFactory.create(
        esp_id="esp_id3",
        email="fake3@email.com",
    )

    track1 = factories.MemberTrackFactory.create(
        user=user1,
        client_track=factories.ClientTrackFactory.create(
            organization=factories.OrganizationFactory(
                name="org1", allowed_tracks=[*TrackName]
            )
        ),
    )
    track2 = factories.MemberTrackFactory.create(
        user=user2,
        client_track=factories.ClientTrackFactory.create(
            organization=factories.OrganizationFactory(
                name="org2", allowed_tracks=[*TrackName]
            )
        ),
    )
    track3 = factories.MemberTrackFactory.create(
        user=user3,
        client_track=factories.ClientTrackFactory.create(
            organization=factories.OrganizationFactory(
                name="org3", allowed_tracks=[TrackName.PREGNANCY]
            )
        ),
    )

    track1.ended_at = datetime.utcnow()
    track2.ended_at = datetime.utcnow()
    track3.ended_at = datetime.utcnow()

    return user1, user2, user3


@pytest.fixture
def incentive_users(factories):
    uoe_1 = factories.UserOrganizationEmployeeFactory()
    user_1 = uoe_1.user

    uoe_2 = factories.UserOrganizationEmployeeFactory()
    user_2 = uoe_2.user

    uoe_3 = factories.UserOrganizationEmployeeFactory()
    user_3 = uoe_3.user

    factories.MemberTrackFactory.create(
        user=user_1,
        client_track=factories.ClientTrackFactory.create(
            organization=factories.OrganizationFactory(
                name="org1", allowed_tracks=[*TrackName]
            )
        ),
    )
    factories.MemberTrackFactory.create(
        user=user_2,
        client_track=factories.ClientTrackFactory.create(
            organization=factories.OrganizationFactory(
                name="org2", allowed_tracks=[*TrackName]
            )
        ),
    )
    factories.MemberTrackFactory.create(
        user=user_3,
        client_track=factories.ClientTrackFactory.create(
            organization=factories.OrganizationFactory(
                name="org3", allowed_tracks=[TrackName.PREGNANCY]
            )
        ),
    )

    # As default member_profile does not come with a country_code
    user_3.member_profile.country_code = "US"
    user_2.member_profile.country_code = "US"
    user_1.member_profile.country_code = "US"

    return user_1, user_2, user_3


@pytest.fixture
def users_and_incentives(factories, incentive_users):
    user_1, user_2, user_3 = incentive_users

    incentive_country_code = user_1.member_profile.country_code
    incentive_track = user_1.current_member_track.name
    incentive_org = user_1.current_member_track.client_track.organization
    incentive_action = IncentiveAction.OFFBOARDING_ASSESSMENT

    incentive_1 = factories.IncentiveFactory.create()
    incentive_organization_1 = factories.IncentiveOrganizationFactory.create(
        incentive=incentive_1,
        organization=incentive_org,
        action=incentive_action,
        track_name=incentive_track,
    )
    factories.IncentiveOrganizationCountryFactory.create(
        incentive_organization=incentive_organization_1,
        country_code=incentive_country_code,
    )

    incentive_country_code_2 = user_2.member_profile.country_code
    incentive_org_2 = user_2.current_member_track.client_track.organization
    incentive_track_2 = user_2.current_member_track.name
    incentive_action_2 = IncentiveAction.OFFBOARDING_ASSESSMENT

    incentive_2 = factories.IncentiveFactory.create()
    incentive_organization_2 = factories.IncentiveOrganizationFactory.create(
        incentive=incentive_2,
        organization=incentive_org_2,
        action=incentive_action_2,
        track_name=incentive_track_2,
    )
    factories.IncentiveOrganizationCountryFactory.create(
        incentive_organization=incentive_organization_2,
        country_code=incentive_country_code_2,
    )

    incentive_country_code_3 = user_3.member_profile.country_code
    incentive_org_3 = user_3.current_member_track.client_track.organization
    incentive_track_3 = user_3.current_member_track.name
    incentive_action_3 = IncentiveAction.OFFBOARDING_ASSESSMENT

    incentive_3 = factories.IncentiveFactory.create()
    incentive_organization_3 = factories.IncentiveOrganizationFactory.create(
        incentive=incentive_3,
        organization=incentive_org_3,
        action=incentive_action_3,
        track_name=incentive_track_3,
    )
    factories.IncentiveOrganizationCountryFactory.create(
        incentive_organization=incentive_organization_3,
        country_code=incentive_country_code_3,
    )

    return user_1, user_2, user_3, incentive_1, incentive_2, incentive_3
