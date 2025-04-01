from unittest.mock import patch

import pytest

from eligibility.e9y import EligibilityVerification
from eligibility.pytests import factories as e9y_factories
from models.tracks import MemberTrack
from tasks.rewards import _is_dependent


@pytest.mark.parametrize(
    argnames="is_employee,dependent_id,expected",
    argvalues=[
        (True, "", False),
        (True, "DEPENDENT", True),
        (True, " ", False),
        (False, "", True),
        (False, "DEPENDENT", True),
        (False, " ", True),
    ],
)
def test_is_dependent(is_employee, dependent_id, expected, factories):
    # Given
    track: MemberTrack = factories.MemberTrackFactory.create(
        name="pregnancy",
        is_employee=is_employee,
    )
    verification: EligibilityVerification = e9y_factories.VerificationFactory.create()
    verification.eligibility_member_id = track.eligibility_member_id
    verification.user_id = track.user_id
    verification.dependent_id = dependent_id

    with patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        user = track.user
        # When
        is_dependent = _is_dependent(user=user, verification=verification)
        # Then
        assert is_dependent == expected
