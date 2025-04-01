from unittest import mock

import pytest

from utils.braze import BrazeUserIncentives
from utils.migrations.braze_users.backfill_offboarding_incentive_id import (
    report_incentive_id_offboarding_to_braze,
)


@pytest.fixture
def patch_send_incentives():
    with mock.patch("utils.braze.send_incentives") as s:
        yield s


@pytest.mark.skip(reason="Flaky")
def test_report_incentive_id_offboarding_to_braze(
    users_and_incentives, patch_send_incentives
):
    user_1, user_2, user_3, incentive_1, incentive_2, incentive_3 = users_and_incentives

    report_incentive_id_offboarding_to_braze(
        org_ids=[
            user_1.current_member_track.client_track.organization.id,
            user_2.current_member_track.client_track.organization.id,
            user_3.current_member_track.client_track.organization.id,
        ],
        dry_run=False,
    )
    patch_send_incentives.assert_called_once_with(
        [
            BrazeUserIncentives(
                incentive_id_ca_intro=None,
                incentive_id_offboarding=incentive_1.id,
                external_id=user_1.esp_id,
            ),
            BrazeUserIncentives(
                incentive_id_ca_intro=None,
                incentive_id_offboarding=incentive_2.id,
                external_id=user_2.esp_id,
            ),
            BrazeUserIncentives(
                incentive_id_ca_intro=None,
                incentive_id_offboarding=incentive_3.id,
                external_id=user_3.esp_id,
            ),
        ]
    )


def test_report_incentive_id_offboarding_to_braze_with_dry_run(
    users_and_incentives, patch_send_incentives
):
    user_1, user_2, user_3, incentive_1, incentive_2, incentive_3 = users_and_incentives

    report_incentive_id_offboarding_to_braze(
        org_ids=[
            user_1.organization.id,
            user_2.organization.id,
            user_3.organization.id,
        ],
        dry_run=True,
    )

    patch_send_incentives.assert_not_called()
