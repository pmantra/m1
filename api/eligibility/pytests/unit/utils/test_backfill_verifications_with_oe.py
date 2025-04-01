import datetime
from unittest import mock

import pytest

from eligibility import EligibilityMemberRepository
from eligibility.pytests import factories as e9y_factories
from eligibility.tasks import backfill_verifications_with_oe as backfill
from models.enterprise import OrganizationEligibilityType


@pytest.fixture
def mock_oe_for_user():
    return backfill.OrganizationEmployeeForUser(
        id=1,
        user_id=1,
        user_organization_employee_id=1,
        organization_employee_id=1,
        organization_id=1,
        oe_member_id=1,
        verification_type=OrganizationEligibilityType.STANDARD,
        unique_corp_id="1",
        dependent_id="1",
        first_name="Fancy",
        last_name="Giraffe",
        date_of_birth=datetime.date(year=2020, month=5, day=2),
        email="long.neck@savethegiraffes.com",
        work_state=None,
        verified_at=None,
        deactivated_at=None,
        e9y_member_id=None,
        e9y_verification_id=None,
        e9y_organization_id=None,
        e9y_unique_corp_id=None,
        e9y_dependent_id=None,
        backfill_status=None,
    )


@pytest.fixture
def mock_e9y_repo():
    return mock.create_autospec(EligibilityMemberRepository)


def test_resolve_backfill_status_not_found(mock_oe_for_user):
    # Given
    # mock_oe_for_user

    # When
    status: backfill.BackfillStatus = backfill._resolve_backfill_status(
        oe_user=mock_oe_for_user, verification=None
    )

    # Then
    assert status == backfill.BackfillStatus.NOT_FOUND


def test_resolve_backfill_status_found_match(mock_oe_for_user):
    # Given
    # mock_oe_for_user
    verification = e9y_factories.VerificationFactory.create(
        organization_id=mock_oe_for_user.organization_id,
    )

    # When
    status: backfill.BackfillStatus = backfill._resolve_backfill_status(
        oe_user=mock_oe_for_user, verification=verification
    )

    # Then
    assert status == backfill.BackfillStatus.ORG_MATCH


def test_resolve_backfill_status_found_no_match(
    factories, mock_e9y_repo, mock_oe_for_user
):
    # Given
    # mock_oe_for_user from fixture

    verification = e9y_factories.VerificationFactory.create(
        organization_id=mock_oe_for_user.organization_id + 1,
    )

    # When
    status: backfill.BackfillStatus = backfill._resolve_backfill_status(
        oe_user=mock_oe_for_user, verification=verification
    )

    # Then
    assert status == backfill.BackfillStatus.ORG_MISMATCH
