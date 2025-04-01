import pytest
import sqlalchemy.exc

from authn.models.user import User
from pytests.factories import EnterpriseUserFactory, MemberBenefitFactory
from wallet.models.member_benefit import MemberBenefit


def test_persist():
    # Given
    user = EnterpriseUserFactory.create(member_benefit=None)
    benefit_id = "MSIJD323D"

    # When
    member_benefit: MemberBenefit = MemberBenefitFactory.create(
        user_id=user.id, benefit_id=benefit_id
    )

    # Then
    assert (member_benefit.benefit_id, user.id) == (
        benefit_id,
        member_benefit.user_id,
    )


def test_persist_user_id_uniqueness():
    # Given
    user = EnterpriseUserFactory.create(member_benefit=None)
    benefit_id = "MSIJD323D"
    another_benefit_id = "MGIJD323D"
    _ = MemberBenefitFactory.create(user_id=user.id, benefit_id=benefit_id)

    # When - Then
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        _ = MemberBenefitFactory.create(user_id=user.id, benefit_id=another_benefit_id)


def test_persist_benefit_id_uniqueness(enterprise_user: User):
    # Given
    another_user = EnterpriseUserFactory.create()

    # When - Then
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        _ = MemberBenefitFactory.create(
            user_id=another_user.id,
            benefit_id=enterprise_user.member_benefit.benefit_id,
        )


def test_persist_started_at_is_not_null():
    # Given
    user = EnterpriseUserFactory.create(member_benefit=None)
    benefit_id = "MSIJD323D"

    # When
    member_benefit: MemberBenefit = MemberBenefitFactory.create(
        user_id=user.id, benefit_id=benefit_id
    )

    # Then
    assert member_benefit.started_at is not None
