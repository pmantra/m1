from unittest import mock

import pytest

from braze import client
from utils.migrations.braze_users.backfill_welcome_box_allowed_gift_card_allowed import (
    report_welcome_box_allowed_gift_card_allowed_to_braze,
)


@pytest.fixture
def patch_send_incentives_allowed():
    with mock.patch("braze.client.BrazeClient.track_users") as s:
        yield s


def test_report_welcome_box_allowed_gift_card_allowed_to_braze(
    patch_send_incentives_allowed, factories
):
    # Given 3 users with organizations that have welcome boxes or gift cards allowed
    user_1 = factories.EnterpriseUserFactory()
    user_1.organization.welcome_box_allowed = True
    user_2 = factories.EnterpriseUserFactory()
    user_2.organization.gift_card_allowed = True
    user_3 = factories.EnterpriseUserFactory()
    user_3.organization.welcome_box_allowed = True
    user_3.organization.gift_card_allowed = True

    # when we attempt to backfill for the relevant orgs
    report_welcome_box_allowed_gift_card_allowed_to_braze(
        org_ids=[
            user_1.organization.id,
            user_2.organization.id,
            user_3.organization.id,
        ],
        dry_run=False,
    )

    expected_attributes = [
        client.BrazeUserAttributes(
            external_id=user_incentive.esp_id,
            attributes={
                "welcome_box_allowed": user_incentive.organization.welcome_box_allowed,
                "gift_card_allowed": user_incentive.organization.gift_card_allowed,
            },
        )
        for user_incentive in [user_1, user_2, user_3]
    ]

    # then the braze call is made with the expected attributes
    patch_send_incentives_allowed.assert_called_once_with(
        user_attributes=expected_attributes
    )


def test_report_welcome_box_allowed_gift_card_allowed_to_braze_with_dry_run(
    patch_send_incentives_allowed,
    factories,
):
    # Given 3 users with organizations that have welcome boxes or gift cards allowed
    user_1 = factories.EnterpriseUserFactory()
    user_1.organization.welcome_box_allowed = True
    user_2 = factories.EnterpriseUserFactory()
    user_2.organization.gift_card_allowed = True
    user_3 = factories.EnterpriseUserFactory()
    user_3.organization.welcome_box_allowed = True
    user_3.organization.gift_card_allowed = True

    # when we call the backfill as a dry run
    report_welcome_box_allowed_gift_card_allowed_to_braze(
        org_ids=[
            user_1.organization.id,
            user_2.organization.id,
            user_3.organization.id,
        ],
        dry_run=True,
    )

    # then we do not send the values to braze
    patch_send_incentives_allowed.assert_not_called()
