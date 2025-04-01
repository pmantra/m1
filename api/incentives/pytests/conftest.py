import pytest
from sqlalchemy import func

from authn.models.user import User
from incentives.models.incentive import IncentiveAction, IncentiveType
from models.tracks import TrackName
from storage.connection import db


@pytest.fixture
def incentive_user(factories):
    """
    A user with all data needed to set up an incentive for it
    """
    organization = factories.OrganizationFactory()
    organization_employee = factories.OrganizationEmployeeFactory(
        organization_id=organization.id
    )
    user = factories.EnterpriseUserNoTracksFactory()
    member_track = factories.MemberTrackFactory(
        user=user,
        client_track=factories.ClientTrackFactory(
            organization=organization,
        ),
    )
    factories.UserOrganizationEmployeeFactory(
        user=user, organization_employee=organization_employee
    )
    user.member_tracks.append(member_track)

    # As default member_profile does not come with a country_code
    user.member_profile.country_code = "US"
    user.member_profile.add_or_update_address(
        {
            "street_address": "160 Varick St",
            "zip_code": "10013",
            "city": "New York",
            "state": "NY",
            "country": "US",
        }
    )
    return user


@pytest.fixture
def invalid_user_id():
    max_user_id = db.session.query(func.max(User.id)).first()[0]
    invalid_user_id = (max_user_id or 0) + 1
    return invalid_user_id


@pytest.fixture
def amazon_incentives(factories):
    incentive_20 = factories.IncentiveFactory.create(
        type=IncentiveType.GIFT_CARD, name="$20 Amazon Gift Card"
    )

    incentive_25 = factories.IncentiveFactory.create(
        type=IncentiveType.GIFT_CARD, name="$25 Amazon Gift Card"
    )

    return [incentive_20, incentive_25]


@pytest.fixture
def user_and_incentive(factories, incentive_user):
    incentive_country_code = incentive_user.member_profile.country_code
    incentive_org = incentive_user.current_member_track.client_track.organization
    incentive_track = incentive_user.current_member_track.name
    incentive_action = IncentiveAction.CA_INTRO

    incentive = factories.IncentiveFactory.create()
    incentive_organization = factories.IncentiveOrganizationFactory.create(
        incentive=incentive,
        organization=incentive_org,
        action=incentive_action,
        track_name=incentive_track,
    )
    factories.IncentiveOrganizationCountryFactory.create(
        incentive_organization=incentive_organization,
        country_code=incentive_country_code,
    )

    return incentive_user, incentive


@pytest.fixture
def user_and_ca_intro_incentive(factories, user_and_incentive):
    # The user_and_incentive fixture comes with a ca_intro incentive by default
    return user_and_incentive


@pytest.fixture
def user_and_offboarding_incentive(factories, incentive_user):
    incentive_country_code = incentive_user.member_profile.country_code
    incentive_org = incentive_user.current_member_track.client_track.organization
    incentive_track = incentive_user.current_member_track.name
    incentive_action = IncentiveAction.OFFBOARDING_ASSESSMENT

    incentive = factories.IncentiveFactory.create()
    incentive_organization = factories.IncentiveOrganizationFactory.create(
        incentive=incentive,
        organization=incentive_org,
        action=incentive_action,
        track_name=incentive_track,
    )
    factories.IncentiveOrganizationCountryFactory.create(
        incentive_organization=incentive_organization,
        country_code=incentive_country_code,
    )

    return incentive_user, incentive


@pytest.fixture
def create_incentive_org(factories, incentive_user):
    def create(**kwargs):
        incentive_type = kwargs.get("incentive_type", IncentiveType.WELCOME_BOX)
        incentive_action = kwargs.get("incentive_action")
        track = kwargs.get("track")
        org = kwargs.get(
            "organization",
            incentive_user.current_member_track.client_track.organization,
        )

        incentive_country_code = incentive_user.member_profile.country_code

        incentive = factories.IncentiveFactory.create(type=incentive_type)
        incentive_organization = factories.IncentiveOrganizationFactory.create(
            incentive=incentive,
            organization=org,
            action=incentive_action,
            track_name=track,
        )
        factories.IncentiveOrganizationCountryFactory.create(
            incentive_organization=incentive_organization,
            country_code=incentive_country_code,
        )

        return incentive_organization

    return create


@pytest.fixture
def user_and_ca_intro_incentive_and_offboarding_incentive(
    factories, user_and_ca_intro_incentive
):
    incentive_user, incentive_ca_intro = user_and_ca_intro_incentive

    incentive_country_code = incentive_user.member_profile.country_code
    incentive_org = incentive_user.current_member_track.client_track.organization
    incentive_track = incentive_user.current_member_track.name
    incentive_action = IncentiveAction.OFFBOARDING_ASSESSMENT

    incentive_offboarding = factories.IncentiveFactory.create()
    incentive_organization = factories.IncentiveOrganizationFactory.create(
        incentive=incentive_offboarding,
        organization=incentive_org,
        action=incentive_action,
        track_name=incentive_track,
    )
    factories.IncentiveOrganizationCountryFactory.create(
        incentive_organization=incentive_organization,
        country_code=incentive_country_code,
    )

    return incentive_user, incentive_ca_intro, incentive_offboarding


@pytest.fixture
def incentive_fulfillment(user_and_incentive, factories):
    # Given a user that has an incentive which has been seen
    user, incentive = user_and_incentive
    incentivized_action = incentive.incentive_organizations[0].action

    incentive_fulfillment = factories.IncentiveFulfillmentFactory.create(
        member_track=user.current_member_track,
        incentive=incentive,
        incentivized_action=incentivized_action,
    )
    return incentive_fulfillment


@pytest.fixture
def incentive_users(factories):
    uoe_1 = factories.UserOrganizationEmployeeFactory()
    user_1 = uoe_1.user

    uoe_2 = factories.UserOrganizationEmployeeFactory()
    user_2 = uoe_2.user

    uoe_3 = factories.UserOrganizationEmployeeFactory()
    user_3 = uoe_3.user

    org = factories.OrganizationFactory(
        name="org1",
    )

    factories.MemberTrackFactory.create(
        user=user_1,
        name=TrackName.PREGNANCY,
        client_track=factories.ClientTrackFactory(organization=org),
    )
    factories.MemberTrackFactory.create(
        user=user_2,
        client_track=factories.ClientTrackFactory(organization=org),
        name=TrackName.POSTPARTUM,
    )
    factories.MemberTrackFactory.create(
        user=user_3,
        client_track=factories.ClientTrackFactory(organization=org),
        name=TrackName.MENOPAUSE,
    )

    # As default member_profile does not come with a country_code
    user_3.member_profile.country_code = "US"
    user_2.member_profile.country_code = "US"
    user_1.member_profile.country_code = "US"

    return user_1, user_2, user_3
