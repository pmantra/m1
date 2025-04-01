from __future__ import annotations

from typing import List

import pytest

from authn.models.user import User
from pytests import factories
from wallet.models.constants import WalletState
from wallet.models.member_benefit import MemberBenefit
from wallet.models.models import MemberBenefitProfile
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.repository.member_benefit import MemberBenefitRepository


@pytest.fixture
def member_benefit_repository(session) -> MemberBenefitRepository:
    return MemberBenefitRepository(session)


def test_add(session, member_benefit_repository: MemberBenefitRepository):
    # given
    user = factories.EnterpriseUserFactory.create(member_benefit=None)

    # when
    benefit_id = member_benefit_repository.add(user_id=user.id)

    # then
    mb: MemberBenefit = session.query(MemberBenefit).filter_by(user_id=user.id).one()

    assert mb.benefit_id == benefit_id


def test_get_by_user_id(
    member_benefit_repository: MemberBenefitRepository, enterprise_user: User
):
    # when
    mb: MemberBenefit = member_benefit_repository.get_by_user_id(
        user_id=enterprise_user.id
    )

    # then
    assert (mb.user_id, mb.benefit_id) == (
        enterprise_user.id,
        enterprise_user.member_benefit.benefit_id,
    )


def test_get_by_benefit_id(
    member_benefit_repository: MemberBenefitRepository, enterprise_user: User
):
    # given
    # when
    mb: MemberBenefit = member_benefit_repository.get_by_benefit_id(
        benefit_id=enterprise_user.member_benefit.benefit_id
    )

    # then
    assert (mb.user_id, mb.benefit_id) == (
        enterprise_user.id,
        enterprise_user.member_benefit.benefit_id,
    )


def test_get_member_benefit_id(
    member_benefit_repository: MemberBenefitRepository, enterprise_user: User
):
    # when
    benefit_id: str | None = member_benefit_repository.get_member_benefit_id(
        user_id=enterprise_user.id
    )

    # then
    assert benefit_id == enterprise_user.member_benefit.benefit_id


def test_get_member_benefit_id_not_found(
    member_benefit_repository: MemberBenefitRepository,
):
    user = factories.EnterpriseUserFactory(member_benefit=None)

    # when
    benefit_id: str | None = member_benefit_repository.get_member_benefit_id(
        user_id=user.id
    )

    # then
    assert not benefit_id


class TestSearchByMemberBenefitId:
    @staticmethod
    def test_search_by_member_benefit_id_not_found(
        member_benefit_repository: MemberBenefitRepository, enterprise_user: User
    ):
        # Given
        date_of_birth = enterprise_user.health_profile.birthday
        last_name = enterprise_user.last_name

        # When
        profile: MemberBenefitProfile = (
            member_benefit_repository.search_by_member_benefit_id(
                last_name=last_name + "huh",
                date_of_birth=date_of_birth,
                benefit_id=enterprise_user.member_benefit.benefit_id,
            )
        )

        # Then
        assert not profile

    @staticmethod
    def test_search_by_member_benefit_id_case_insensitive(
        member_benefit_repository: MemberBenefitRepository, enterprise_user: User
    ):
        # Given
        date_of_birth = enterprise_user.health_profile.birthday
        last_name = enterprise_user.last_name

        # When
        profile: MemberBenefitProfile = (
            member_benefit_repository.search_by_member_benefit_id(
                last_name=last_name.upper(),
                date_of_birth=date_of_birth,
                benefit_id=enterprise_user.member_benefit.benefit_id,
            )
        )

        # Then
        assert profile.user_id == enterprise_user.id

    @staticmethod
    def test_search_by_member_benefit_id(
        member_benefit_repository: MemberBenefitRepository, enterprise_user: User
    ):
        # Given
        date_of_birth = enterprise_user.health_profile.birthday
        last_name = enterprise_user.last_name

        # When
        profile: MemberBenefitProfile = (
            member_benefit_repository.search_by_member_benefit_id(
                last_name=last_name,
                date_of_birth=date_of_birth,
                benefit_id=enterprise_user.member_benefit.benefit_id,
            )
        )

        # Then
        assert profile == MemberBenefitProfile(
            user_id=enterprise_user.id,
            benefit_id=enterprise_user.member_benefit.benefit_id,
            date_of_birth=enterprise_user.health_profile.birthday,
            email=enterprise_user.email,
            first_name=enterprise_user.first_name,
            last_name=enterprise_user.last_name,
            phone=enterprise_user.member_profile.phone_number,
        )


class TestGetByWalletId:
    @staticmethod
    def test_get_by_wallet_id_single_user_no_member_benefit(
        member_benefit_repository: MemberBenefitRepository,
    ):
        # Given
        user = factories.EnterpriseUserFactory(member_benefit=None)
        wallet = ReimbursementWalletFactory.create(
            member=user, state=WalletState.QUALIFIED
        )
        ReimbursementWalletUsersFactory.create(
            user_id=user.id,
            reimbursement_wallet_id=wallet.id,
            zendesk_ticket_id=1234,
        )
        # When
        member_benefits: List[
            MemberBenefit
        ] = member_benefit_repository.get_by_wallet_id(wallet_id=wallet.id)

        # Then
        assert not member_benefits

    @staticmethod
    def test_get_by_wallet_id_single_user(
        member_benefit_repository: MemberBenefitRepository,
        active_wallet_user: ReimbursementWalletUsers,
        qualified_wallet: ReimbursementWallet,
    ):
        # Given an active wallet user
        member_benefit_repository.add(user_id=active_wallet_user.user_id)

        # When
        member_benefits: List[
            MemberBenefit
        ] = member_benefit_repository.get_by_wallet_id(wallet_id=qualified_wallet.id)

        # Then
        assert member_benefits
