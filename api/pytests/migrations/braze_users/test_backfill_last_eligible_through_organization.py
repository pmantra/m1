from unittest import mock

import pytest

from utils.braze import BrazeEligibleThroughOrganization
from utils.migrations.braze_users.backfill_last_eligible_through_organization import (
    report_last_eligible_through_organization_to_braze,
)


@pytest.fixture
def patch_send_last_eligible_through_organizations():
    with mock.patch("utils.braze.send_last_eligible_through_organizations") as s:
        yield s


def test_report_last_eligible_through_organization_to_braze(
    fake_enterprise_users, patch_send_last_eligible_through_organizations
):
    report_last_eligible_through_organization_to_braze(
        dry_run=False, page_size=2, page_limit=None
    )

    assert patch_send_last_eligible_through_organizations.call_count == 2
    patch_send_last_eligible_through_organizations.assert_has_calls(
        [
            mock.call(
                [
                    BrazeEligibleThroughOrganization(
                        fake_enterprise_users[0].esp_id,
                        fake_enterprise_users[
                            0
                        ].organization_employee.organization.name,
                    ),
                    BrazeEligibleThroughOrganization(
                        fake_enterprise_users[1].esp_id,
                        fake_enterprise_users[
                            1
                        ].organization_employee.organization.name,
                    ),
                ]
            ),
            mock.call(
                [
                    BrazeEligibleThroughOrganization(
                        fake_enterprise_users[2].esp_id,
                        fake_enterprise_users[
                            2
                        ].organization_employee.organization.name,
                    )
                ]
            ),
        ]
    )


def test_report_last_eligible_through_organization_to_braze_with_page_limit(
    fake_enterprise_users, patch_send_last_eligible_through_organizations
):
    report_last_eligible_through_organization_to_braze(
        dry_run=False, page_size=1, page_limit=1
    )
    assert patch_send_last_eligible_through_organizations.call_count == 1


def test_report_last_eligible_through_organization_to_braze_with_dry_run(
    fake_enterprise_users, patch_send_last_eligible_through_organizations
):
    report_last_eligible_through_organization_to_braze(
        dry_run=True, page_size=50, page_limit=None
    )
    patch_send_last_eligible_through_organizations.assert_not_called()
