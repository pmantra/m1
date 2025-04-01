from unittest import mock

from authn.models.user import User
from wallet.models.constants import DashboardState, MemberType, WalletState
from wallet.models.models import (
    BenefitResourceSchema,
    EligibleWalletSchema,
    EnrolledWalletSchema,
    MemberWalletStateSchema,
    ReimbursementWalletStateSummarySchema,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet


def test_get_reimbursement_wallet_state_success(
    client,
    api_helpers,
    enterprise_user: User,
    qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
):
    # Given

    # When
    res = client.get(
        "/api/v1/reimbursement_wallet/state",
        headers=api_helpers.json_headers(enterprise_user),
    )

    # Then
    assert res.status_code == 200


def test_get_reimbursement_wallet_state_error(
    client,
    api_helpers,
    enterprise_user: User,
    qualified_alegeus_wallet_hdhp_single: ReimbursementWallet,
):
    # Given

    # When
    with mock.patch(
        "wallet.services.reimbursement_wallet.ReimbursementWalletService.get_member_wallet_state"
    ) as mock_get_member_wallet_state:
        mock_get_member_wallet_state.side_effect = Exception("A generic exception!")
        res = client.get(
            "/api/v1/reimbursement_wallet/state",
            headers=api_helpers.json_headers(enterprise_user),
        )

    # Then
    assert res.status_code == 500


def test_get_reimbursement_wallet_state_schema():
    # Given
    mws = MemberWalletStateSchema(
        summary=ReimbursementWalletStateSummarySchema(
            show_wallet=True,
            member_type=MemberType.MAVEN_GREEN,
            dashboard_state=DashboardState.PENDING,
            member_benefit_id="M00000000",
        ),
        eligible=[
            EligibleWalletSchema(
                organization_setting_id=1,
                survey_url="www.takethissurvey.com",
                benefit_faq_resource=BenefitResourceSchema(
                    url="www.coolresource.com", title="Cool Resource"
                ),
                benefit_overview_resource=BenefitResourceSchema(
                    url="www.evencoolerresource.com", title="Even Cooler Resource"
                ),
            )
        ],
        enrolled=[
            EnrolledWalletSchema(
                wallet_id=1,
                state=WalletState.QUALIFIED,
                channel_id=1,
                benefit_faq_resource=BenefitResourceSchema(
                    url="www.coolresource.com", title="Cool Resource"
                ),
                benefit_overview_resource=BenefitResourceSchema(
                    url="www.evencoolerresource.com", title="Even Cooler Resource"
                ),
            )
        ],
    )

    # When
    expected_schema = mws.serialize()

    # Then
    assert expected_schema == {
        "summary": {
            "show_wallet": mock.ANY,
            "member_type": mock.ANY,
            "dashboard_state": mock.ANY,
            "member_benefit_id": mock.ANY,
            "wallet_id": mock.ANY,
            "channel_id": mock.ANY,
            "is_shareable": mock.ANY,
            "pharmacy": mock.ANY,
        },
        "eligible": [
            {
                "organization_setting_id": mock.ANY,
                "survey_url": mock.ANY,
                "wallet_id": mock.ANY,
                "state": mock.ANY,
                "benefit_overview_resource": mock.ANY,
                "benefit_faq_resource": mock.ANY,
            }
        ],
        "enrolled": [
            {
                "wallet_id": mock.ANY,
                "state": mock.ANY,
                "channel_id": mock.ANY,
                "benefit_overview_resource": mock.ANY,
                "benefit_faq_resource": mock.ANY,
            }
        ],
    }
