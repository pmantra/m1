import datetime
from unittest.mock import patch

import pytest

from braze import BrazeUserAttributes, format_dt
from models.enterprise import OnboardingState
from utils import braze
from utils.braze import (
    BrazeEligibleThroughOrganization,
    BrazeUserIncentives,
    BrazeUserOnboardingState,
)


def test_build_user_attrs_has_pnp(factories):
    track = factories.MemberTrackFactory()
    pnp_track = factories.MemberTrackFactory(
        name="parenting_and_pediatrics", user=track.user
    )

    attrs = braze.build_user_attrs(track.user).attributes
    assert attrs["pnp_track_started"] == format_dt(pnp_track.created_at)


def test_build_user_attrs_no_pnp(factories):
    user = factories.EnterpriseUserFactory()
    attrs = braze.build_user_attrs(user).attributes
    assert attrs["pnp_track_started"] is None


@patch("braze.client.BrazeClient.track_user")
def test_send_onboarding_state(mock_request):
    external_id = "esp_id"
    onboarding_state = OnboardingState.USER_CREATED

    braze_user_attributes = BrazeUserAttributes(
        external_id=external_id,
        attributes={"onboarding_state": onboarding_state},
    )

    braze.send_onboarding_state(external_id, onboarding_state)

    mock_request.assert_called_with(
        user_attributes=braze_user_attributes,
    )


@patch("braze.client.BrazeClient.track_users")
def test_send_onboarding_states(mock_request):
    user_onboarding_states = [
        BrazeUserOnboardingState("1", OnboardingState.USER_CREATED),
        BrazeUserOnboardingState("2", OnboardingState.FAILED_TRACK_SELECTION),
    ]

    braze_user_attributes = [
        BrazeUserAttributes(
            external_id=uos.external_id,
            attributes={"onboarding_state": uos.onboarding_state},
        )
        for uos in user_onboarding_states
    ]

    braze.send_onboarding_states(user_onboarding_states)

    mock_request.assert_called_with(
        user_attributes=braze_user_attributes,
    )


@patch("braze.client.BrazeClient.track_user")
def test_send_last_eligible_through_organization(mock_request):
    external_id = "esp_id"
    organization_name = "ACME"

    braze_user_attributes = BrazeUserAttributes(
        external_id=external_id,
        attributes={"last_eligible_through_organization": organization_name},
    )

    braze.send_last_eligible_through_organization(external_id, organization_name)

    mock_request.assert_called_with(
        user_attributes=braze_user_attributes,
    )


@patch("braze.client.BrazeClient.track_users")
def test_send_last_eligible_through_organizations(mock_request):
    last_eligible_through_organizations = [
        BrazeEligibleThroughOrganization("1", "ACME"),
        BrazeEligibleThroughOrganization("2", "ACMEv2"),
    ]

    braze_user_attributes = [
        BrazeUserAttributes(
            external_id=x.external_id,
            attributes={
                "last_eligible_through_organization": x.last_eligible_through_organization,
            },
        )
        for x in last_eligible_through_organizations
    ]

    braze.send_last_eligible_through_organizations(last_eligible_through_organizations)

    mock_request.assert_called_with(
        user_attributes=braze_user_attributes,
    )


@patch("braze.client.BrazeClient.track_user")
def test_send_incentive(mock_request):
    # given an external id, and incentive ids for ca intro and offboarding
    external_id = "esp_id"
    incentive_id_ca_intro = 1
    incentive_offboarding = 2

    # when we call braze send incentive
    braze.send_incentive(external_id, incentive_id_ca_intro, incentive_offboarding)

    braze_user = BrazeUserAttributes(
        external_id=external_id,
        attributes={
            "incentive_id_ca_intro": incentive_id_ca_intro,
            "incentive_id_offboarding": incentive_offboarding,
        },
    )

    # the user attributes are sent to the braze user track endpoint
    mock_request.assert_called_with(
        user_attributes=braze_user,
    )


@patch("braze.client.BrazeClient.track_users")
def test_send_incentives(mock_request):
    # given two instances of braze user with ca intro and offboarding incentives
    incentives = [
        BrazeUserIncentives("1", 3, 5),
        BrazeUserIncentives("2", 4, 6),
    ]

    braze_users = [
        BrazeUserAttributes(
            external_id=bui.external_id,
            attributes={
                "incentive_id_ca_intro": bui.incentive_id_ca_intro,
                "incentive_id_offboarding": bui.incentive_id_offboarding,
            },
        )
        for bui in incentives
    ]

    # when we call braze send incentives
    braze.send_incentives(incentives)

    # the user attributes are sent to the braze user track endpoint
    mock_request.assert_called_with(
        user_attributes=braze_users,
    )


@patch("braze.client.BrazeClient.track_user")
def test_send_incentives_allowed(mock_request):
    # given an external id, and values for welcome_box_allowed and gift_card_allowed
    external_id = "esp_id"
    welcome_box_allowed = True
    gift_card_allowed = True

    braze_user = BrazeUserAttributes(
        external_id=external_id,
        attributes={
            "welcome_box_allowed": welcome_box_allowed,
            "gift_card_allowed": gift_card_allowed,
        },
    )

    # when we call braze send_incentives_allowed
    braze.send_incentives_allowed(external_id, welcome_box_allowed, gift_card_allowed)

    # the user attributes are sent to the braze user track endpoint
    mock_request.assert_called_with(
        user_attributes=braze_user,
    )


@patch("braze.client.BrazeClient._make_request")
@pytest.mark.parametrize(
    "external_id, wallet_qualification_datetime, wallet_added_payment_method_datetime,wallet_added_health_insurance_datetime, exp_called, exp_data",
    [
        pytest.param(
            "esp_id_1",
            datetime.datetime(2025, 1, 1, 10, 59, tzinfo=datetime.timezone.utc),
            datetime.datetime(2025, 2, 1, 14, 1, tzinfo=datetime.timezone.utc),
            datetime.datetime(2025, 5, 1, 14, 1, tzinfo=datetime.timezone.utc),
            True,
            {
                "external_id": "esp_id_1",
                "wallet_qualification_datetime": datetime.datetime(
                    2025, 1, 1, 10, 59, tzinfo=datetime.timezone.utc
                ).isoformat(),
                "wallet_added_payment_method_datetime": datetime.datetime(
                    2025, 2, 1, 14, 1, tzinfo=datetime.timezone.utc
                ).isoformat(),
                "wallet_added_health_insurance_datetime": datetime.datetime(
                    2025, 5, 1, 14, 1, tzinfo=datetime.timezone.utc
                ).isoformat(),
            },
            id="1. All params populated",
        ),
        pytest.param(
            "esp_id", None, None, None, False, None, id="2. No data, no call."
        ),
        pytest.param(
            "", None, None, None, False, None, id="3. Blank external id, no call."
        ),
        pytest.param(
            "esp_id_2",
            datetime.datetime(2025, 1, 1, 10, 59, tzinfo=datetime.timezone.utc),
            None,
            None,
            True,
            {
                "external_id": "esp_id_2",
                "wallet_qualification_datetime": datetime.datetime(
                    2025, 1, 1, 10, 59, tzinfo=datetime.timezone.utc
                ).isoformat(),
            },
            id="4. No payment method or health insurance info",
        ),
        pytest.param(
            "esp_id_3",
            datetime.datetime(2025, 1, 1, 10, 59, tzinfo=datetime.timezone.utc),
            None,
            datetime.datetime(2025, 5, 1, 14, 1, tzinfo=datetime.timezone.utc),
            True,
            {
                "external_id": "esp_id_3",
                "wallet_qualification_datetime": datetime.datetime(
                    2025, 1, 1, 10, 59, tzinfo=datetime.timezone.utc
                ).isoformat(),
                "wallet_added_health_insurance_datetime": datetime.datetime(
                    2025, 5, 1, 14, 1, tzinfo=datetime.timezone.utc
                ).isoformat(),
            },
            id="5. Health insurance provided. payment method missing",
        ),
    ],
)
def test_send_wallet_user_attributes(
    mock_request,
    external_id: str,
    wallet_qualification_datetime,
    wallet_added_payment_method_datetime,
    wallet_added_health_insurance_datetime,
    exp_called,
    exp_data,
):
    braze.send_user_wallet_attributes(
        external_id=external_id,
        wallet_qualification_datetime=wallet_qualification_datetime,
        wallet_added_payment_method_datetime=wallet_added_payment_method_datetime,
        wallet_added_health_insurance_datetime=wallet_added_health_insurance_datetime,
    )

    assert mock_request.called == exp_called
    if exp_called:
        assert "data" in mock_request.call_args.kwargs
        assert mock_request.call_args.kwargs["data"]["attributes"][0] == exp_data
