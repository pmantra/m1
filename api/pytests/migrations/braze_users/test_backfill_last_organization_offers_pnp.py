from unittest import mock

from braze import BrazeUserAttributes
from utils.migrations.braze_users.backfill_last_organization_offers_pnp import (
    report_last_organization_offers_pnp_to_braze,
)


@mock.patch("braze.client.BrazeClient.track_users")
def test_report_last_eligible_through_organization_to_braze(
    mock_track_users,
    fake_enterprise_users,
):
    report_last_organization_offers_pnp_to_braze(
        dry_run=False, page_size=1, page_limit=None
    )

    expected_users = [
        BrazeUserAttributes(
            external_id=fake_enterprise_users[0].esp_id,
            attributes={"last_organization_offers_pnp": True},
        ),
        BrazeUserAttributes(
            external_id=fake_enterprise_users[1].esp_id,
            attributes={"last_organization_offers_pnp": True},
        ),
    ]

    assert mock_track_users.call_count == 2
    mock_track_users.assert_has_calls(
        [
            mock.call(user_attributes=[expected_users[0]]),
            mock.call(user_attributes=[expected_users[1]]),
        ]
    )


@mock.patch("braze.client.BrazeClient.track_users")
def test_report_last_eligible_through_organization_to_braze_with_dry_run(
    mock_track_users,
    fake_enterprise_users,
):
    report_last_organization_offers_pnp_to_braze(
        dry_run=True, page_size=50, page_limit=None
    )
    mock_track_users.assert_not_called()
