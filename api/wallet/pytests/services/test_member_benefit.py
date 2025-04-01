from unittest import mock

import pytest

from authn.models.user import User
from wallet.models.member_benefit import MemberBenefit
from wallet.services.member_benefit import MemberBenefitService


@pytest.fixture()
def mock_member_benefit_repository():
    with mock.patch(
        "wallet.repository.member_benefit.MemberBenefitRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture
def member_benefit_service(mock_member_benefit_repository):
    return MemberBenefitService(member_benefit_repo=mock_member_benefit_repository)


def test_add_for_user_success(
    member_benefit_service: MemberBenefitService, enterprise_user: User
):
    # Given
    benefit_id: str = "M000000000"
    expected_member_benefit: MemberBenefit = MemberBenefit(
        benefit_id=benefit_id, user_id=enterprise_user.id
    )
    member_benefit_service.member_benefit_repo.add.return_value = (
        expected_member_benefit
    )

    # When
    member_benefit = member_benefit_service.add_for_user(user_id=enterprise_user.id)

    # Then
    assert member_benefit == expected_member_benefit


def test_add_for_user_raises_unknown_exception(
    member_benefit_service: MemberBenefitService, enterprise_user: User
):
    # Given
    member_benefit_service.member_benefit_repo.add.side_effect = Exception(
        "What the heck?"
    )

    # When - Then
    with pytest.raises(Exception, match="What the heck?"):
        member_benefit_service.add_for_user(user_id=enterprise_user.id)
