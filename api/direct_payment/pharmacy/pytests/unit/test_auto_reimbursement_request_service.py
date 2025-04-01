from datetime import datetime, timedelta
from unittest.mock import patch

import pytest as pytest
from requests import Response

from cost_breakdown.constants import AmountType, CostBreakdownType
from cost_breakdown.errors import (
    ActionableCostBreakdownException,
    CreateDirectPaymentClaimErrorResponseException,
)
from cost_breakdown.models.cost_breakdown import CostBreakdown
from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    CostBreakdownIrsMinimumDeductibleFactory,
)
from direct_payment.pharmacy.errors import NoReimbursementMethodError
from direct_payment.pharmacy.pytests.factories import PharmacyPrescriptionFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from wallet.models.constants import (
    CostSharingCategory,
    ReimbursementMethod,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    TaxationStateConfig,
    WalletUserMemberStatus,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.pytests.factories import (
    ReimbursementClaimFactory,
    ReimbursementOrgSettingsExpenseTypeFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletUsersFactory,
)


@pytest.fixture(scope="function")
def rr_cost_breakdown_data():
    def _rr_cost_breakdown_data(
        total_member_responsibility,
        total_employer_responsibility,
        reimbursement_request,
        deductible=1000,
    ):
        return CostBreakdown(
            wallet_id=reimbursement_request.reimbursement_wallet_id,
            member_id=reimbursement_request.person_receiving_service_id,
            reimbursement_request_id=reimbursement_request.id,
            total_member_responsibility=total_member_responsibility,
            total_employer_responsibility=total_employer_responsibility,
            beginning_wallet_balance=100000,
            ending_wallet_balance=90000,
            deductible=deductible,
            deductible_remaining=0,
            family_deductible_remaining=0,
            coinsurance=2000,
            copay=None,
            oop_applied=3000,
            oop_remaining=None,
            family_oop_remaining=None,
            overage_amount=None,
            amount_type=AmountType.INDIVIDUAL,
            cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
            rte_transaction_id=1,
            calc_config={},
        )

    return _rr_cost_breakdown_data


@pytest.fixture()
def wallet_users(wallet):
    return ReimbursementWalletUsersFactory.create(
        user_id=wallet.user_id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )


class TestAutomatedReimbursementRequestService:
    def test_get_reimbursement_request_found(
        self, automated_reimbursement_request_service, new_prescription, wallet_users
    ):
        # Given
        given_pharmacy_prescription = new_prescription()
        # When
        found_reimbursement_request = (
            automated_reimbursement_request_service.get_reimbursement_request(
                pharmacy_prescription=given_pharmacy_prescription
            )
        )
        # Then
        assert (
            found_reimbursement_request.id
            == given_pharmacy_prescription.reimbursement_request_id
        )

    def test_get_reimbursement_request_none(
        self, automated_reimbursement_request_service, new_prescription, wallet_users
    ):
        # Given
        given_pharmacy_prescription = new_prescription(reimbursement_request_id=None)
        # When
        found_reimbursement_request = (
            automated_reimbursement_request_service.get_reimbursement_request(
                pharmacy_prescription=given_pharmacy_prescription
            )
        )
        # Then
        assert found_reimbursement_request is None

    def test_get_cost_breakdown_from_reimbursement_request(
        self,
        automated_reimbursement_request_service,
        rx_cost_breakdown_for_reimbursement_request,
        rx_reimbursement_request,
        wallet_users,
    ):
        # Given
        given_reimbursement_request_id = rx_reimbursement_request.id
        given_cost_breakdown_id = rx_cost_breakdown_for_reimbursement_request.id

        # When
        found_cost_breakdown = automated_reimbursement_request_service.get_cost_breakdown_from_reimbursement_request(
            reimbursement_request_id=given_reimbursement_request_id
        )

        # Then
        assert found_cost_breakdown.id == given_cost_breakdown_id

    def test_get_cost_breakdown_from_reimbursement_request_none(
        self,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet_users,
    ):
        # Given
        given_reimbursement_request_id = rx_reimbursement_request.id

        # When
        found_cost_breakdown = automated_reimbursement_request_service.get_cost_breakdown_from_reimbursement_request(
            reimbursement_request_id=given_reimbursement_request_id
        )

        # Then
        assert found_cost_breakdown is None

    def test_get_member_status(
        self, wallet, automated_reimbursement_request_service, wallet_users
    ):
        # Given/When
        member_status = automated_reimbursement_request_service.get_member_status(
            user_id=wallet.user_id, wallet_id=wallet.id
        )
        # Then
        assert member_status == WalletUserMemberStatus.MEMBER

    def test_get_reimbursement_request_cost_breakdown(
        self,
        wallet,
        individual_member_health_plan,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet_users,
    ):
        # Given / When
        cb = automated_reimbursement_request_service.get_reimbursement_request_cost_breakdown(
            reimbursement_request=rx_reimbursement_request, user_id=wallet.user_id
        )
        # Then
        assert cb

    def test_get_reimbursement_request_cost_breakdown_hdhp(
        self,
        wallet,
        individual_member_health_plan,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet_users,
    ):
        # Given
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            False
        )
        individual_member_health_plan.employer_health_plan.is_hdhp = True
        CostBreakdownIrsMinimumDeductibleFactory.create(
            individual_amount=150_000,
            family_amount=300_000,
        )
        # When
        cb = automated_reimbursement_request_service.get_reimbursement_request_cost_breakdown(
            reimbursement_request=rx_reimbursement_request, user_id=wallet.user_id
        )
        # Then
        assert cb

    def test_get_reimbursement_request_cost_breakdown_fully_covered_cycles(
        self,
        wallet_cycle_based,
        enterprise_user,
        automated_reimbursement_request_service,
    ):
        # Given
        category_association = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ]
        category_association.reimbursement_request_category_maximum = 10000
        category = category_association.reimbursement_request_category
        rr = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=wallet_cycle_based.id,
            reimbursement_request_category_id=category.id,
            reimbursement_type=ReimbursementRequestType.MANUAL,
            procedure_type=TreatmentProcedureType.PHARMACY.value,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            person_receiving_service_id=wallet_cycle_based.user_id,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            cost_credit=0,
            amount=5000,
        )
        # When
        cb = automated_reimbursement_request_service.get_reimbursement_request_cost_breakdown(
            reimbursement_request=rr, user_id=wallet_cycle_based.user_id
        )
        # Then
        assert cb

    def test_get_reimbursement_request_cost_breakdown_fails(
        self,
        wallet,
        individual_member_health_plan,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet_users,
    ):
        # Given
        reimbursement_request = rx_reimbursement_request
        reimbursement_request.cost_sharing_category = None
        # When/Then
        with pytest.raises(ActionableCostBreakdownException) as e:
            automated_reimbursement_request_service.get_reimbursement_request_cost_breakdown(
                reimbursement_request=rx_reimbursement_request, user_id=wallet.user_id
            )
        assert (
            e.value.message
            == "Must provide a Cost Sharing category or a Global Procedure id to calculate Cost "
            "Breakdown."
        )

    @pytest.mark.parametrize(
        "request_amount,member_responsibility,employer_responsibility,expected_amount,expected_state",
        [
            # member responsibility == amount
            (3000, 3000, 0, 3000, ReimbursementRequestState.DENIED),
            # divided responsibility
            (2000, 1000, 1000, 1000, ReimbursementRequestState.APPROVED),
            # employer responsibility == amount
            (3000, 0, 3000, 3000, ReimbursementRequestState.APPROVED),
        ],
        ids=[
            "full_member_responsibility",
            "divided_responsibility",
            "full_employer_responsibility",
        ],
    )
    def test_update_reimbursement_request_from_cost_breakdown(
        self,
        request_amount,
        member_responsibility,
        employer_responsibility,
        expected_amount,
        expected_state,
        wallet,
        individual_member_health_plan,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        rr_cost_breakdown_data,
        wallet_users,
    ):
        # Given
        given_reimbursement_request = rx_reimbursement_request
        given_reimbursement_request.amount = request_amount
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=member_responsibility,
            total_employer_responsibility=employer_responsibility,
            reimbursement_request=given_reimbursement_request,
        )
        # When
        cb_reimbursement_request = automated_reimbursement_request_service.update_reimbursement_request_from_cost_breakdown(
            cost_breakdown=cost_breakdown,
            reimbursement_request=given_reimbursement_request,
        )
        # Then
        assert cb_reimbursement_request.amount == expected_amount
        assert cb_reimbursement_request.state == expected_state

    @pytest.mark.parametrize(
        "deductible_accumulation_enabled,is_hdhp,deductible,expected_result",
        [
            # Test case 1: Deductible accumulation is enabled, should return False
            (
                True,  # deductible_accumulation_enabled
                True,  # is_hdhp
                None,  # deductible
                False,  # expected_result
            ),
            # Test case 2: HDHP is True, no existing claims, deductible > 0, should return True
            (
                False,  # deductible_accumulation_enabled
                True,  # is_hdhp
                500,  # deductible
                True,  # expected_result
            ),
            # Test case 3: HDHP is True,  deductible is None, should return False
            (
                False,  # deductible_accumulation_enabled
                True,  # is_hdhp
                None,  # deductible
                False,  # expected_result
            ),
            # Test case 4: HDHP is False, should return False
            (
                False,  # deductible_accumulation_enabled
                False,  # is_hdhp
                None,  # deductible
                False,  # expected_result
            ),
        ],
    )
    def test_should_submit_dtr_claim(
        self,
        deductible_accumulation_enabled,
        is_hdhp,
        deductible,
        expected_result,
        wallet,
        individual_member_health_plan,
        rx_reimbursement_request,
        rr_cost_breakdown_data,
        automated_reimbursement_request_service,
        wallet_users,
    ):
        # Given
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            deductible_accumulation_enabled
        )
        individual_member_health_plan.employer_health_plan.is_hdhp = is_hdhp
        given_reimbursement_request = rx_reimbursement_request
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=1000,
            total_employer_responsibility=1000,
            reimbursement_request=given_reimbursement_request,
            deductible=deductible,
        )
        # When
        result = automated_reimbursement_request_service.should_submit_dtr_claim(
            given_reimbursement_request, cost_breakdown
        )
        # Then
        assert result == expected_result

    @pytest.mark.parametrize(
        "da_enabled,claim_amount,deductible,expected_result",
        [
            # Test case 1: DA enabled = True should return False
            (
                True,  # DA enabled
                1000,  # claim amount
                1000,  # deductible
                False,  # expected_result
            ),
            # Test case 2: # claim amount and deductible different, should return False
            (
                False,  # DA not enabled
                500,  # claim amount
                1000,  # deductible
                False,  # expected_result
            ),
            # Test case 3: claim amount == total member responsibility, should return False
            (
                False,  # DA not enabled
                1000,  # claim amount
                1000,  # deductible
                False,  # expected_result
            ),
            # Test case 4: claim amount == total employer responsibility and no deductible amount, return False
            (
                False,  # DA not enabled
                1000,  # claim amount
                0,  # deductible
                False,  # expected_result
            ),
        ],
    )
    def test_should_submit_dtr_claim_with_claims(
        self,
        da_enabled,
        claim_amount,
        deductible,
        expected_result,
        wallet,
        individual_member_health_plan,
        rx_reimbursement_request,
        rr_cost_breakdown_data,
        automated_reimbursement_request_service,
        wallet_users,
    ):
        # Given
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            da_enabled
        )
        individual_member_health_plan.employer_health_plan.is_hdhp = True
        given_reimbursement_request = rx_reimbursement_request
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=1000,
            total_employer_responsibility=1000,
            reimbursement_request=given_reimbursement_request,
            deductible=deductible,
        )
        ReimbursementClaimFactory.create(
            alegeus_claim_id="123abc",
            alegeus_claim_key=1,
            status="Approved",
            reimbursement_request=given_reimbursement_request,
            amount=claim_amount,
        )
        # When
        result = automated_reimbursement_request_service.should_submit_dtr_claim(
            given_reimbursement_request, cost_breakdown
        )
        # Then
        assert result == expected_result

    @pytest.mark.parametrize(
        "rr_state,total_employer_responsibility,expected_result",
        [
            # Test case 1: RR state is Approved, total employer res > 0, should return True
            (
                ReimbursementRequestState.APPROVED,  # rr_state
                500,  # total_employer_responsibility
                True,  # expected result
            ),
            # Test case 2: RR state is Denied, total employer res > 0, should return False
            (
                ReimbursementRequestState.DENIED,  # rr_state
                500,  # total_employer_responsibility
                False,  # expected result
            ),
            # Test case 3: RR state is Approved, total employer res = 0, should return False
            (
                ReimbursementRequestState.APPROVED,  # rr_state
                0,  # total_employer_responsibility
                False,  # expected result
            ),
        ],
    )
    def test_should_submit_hra_claim(
        self,
        rr_state,
        total_employer_responsibility,
        expected_result,
        wallet,
        individual_member_health_plan,
        rx_reimbursement_request,
        rr_cost_breakdown_data,
        automated_reimbursement_request_service,
        wallet_users,
    ):
        # Given
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            False
        )
        given_reimbursement_request = rx_reimbursement_request
        given_reimbursement_request.state = rr_state
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=1000,
            total_employer_responsibility=total_employer_responsibility,
            reimbursement_request=given_reimbursement_request,
        )
        # When
        result = automated_reimbursement_request_service.should_submit_hra_claim(
            given_reimbursement_request, cost_breakdown
        )
        # Then
        assert result == expected_result

    def test_get_reimbursement_method_org_settings(
        self, wallet, automated_reimbursement_request_service, wallet_users
    ):
        # Given wallet is set to PAYROLL
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        request_category = category_association.reimbursement_request_category
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=request_category,
            expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
        )
        ReimbursementOrgSettingsExpenseTypeFactory.create(
            reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
            expense_type=expense_type,
            taxation_status=TaxationStateConfig.SPLIT_DX_INFERTILITY,
            reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
        )
        # When
        result = automated_reimbursement_request_service.get_reimbursement_method(
            wallet, expense_type
        )
        # Then
        assert result == ReimbursementMethod.DIRECT_DEPOSIT

    def test_get_reimbursement_method_wallet(
        self, wallet, automated_reimbursement_request_service, wallet_users
    ):
        # Given
        category = ReimbursementRequestCategoryFactory.create(label="Random Category")
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.MENOPAUSE,
        )
        expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        # When
        result = automated_reimbursement_request_service.get_reimbursement_method(
            wallet, expense_type
        )
        # Then
        assert result == ReimbursementMethod.PAYROLL

    def test_get_reimbursement_method_none(
        self, wallet, automated_reimbursement_request_service, wallet_users
    ):
        # Given
        expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        wallet.reimbursement_method = None
        # When/Then
        with pytest.raises(NoReimbursementMethodError):
            automated_reimbursement_request_service.get_reimbursement_method(
                wallet, expense_type
            )

    @pytest.mark.parametrize(
        "dtr,hra,expected_len",
        [
            (True, False, 1),
            (False, True, 1),
            (True, True, 2),
        ],
    )
    def test__get_requests_to_process(
        self,
        dtr,
        hra,
        expected_len,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet_users,
    ):
        # Given
        given_reimbursement_request = rx_reimbursement_request
        # When
        results = automated_reimbursement_request_service._get_requests_to_process(
            should_submit_dtr=dtr,
            should_submit_hra=hra,
            reimbursement_request=given_reimbursement_request,
            reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
        )
        # Then
        assert len(results) == expected_len

    @pytest.mark.parametrize(
        "deductible_acc_enabled,is_hdhp,expected_requests_to_alegeus",
        [
            # HRA and DTR
            (False, True, 2),
            # Only HRA
            (True, False, 1),
            # Only HRA
            (False, False, 1),
        ],
    )
    def test_submit_auto_processed_request_to_alegeus_success(
        self,
        deductible_acc_enabled,
        is_hdhp,
        expected_requests_to_alegeus,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet,
        rr_cost_breakdown_data,
        mocked_auto_processed_claim_response,
        individual_member_health_plan,
        wallet_users,
    ):
        # Given
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            deductible_acc_enabled
        )
        individual_member_health_plan.employer_health_plan.is_hdhp = is_hdhp
        given_reimbursement_request = rx_reimbursement_request
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=3500,
            total_employer_responsibility=1500,
            reimbursement_request=given_reimbursement_request,
            deductible=3000,
        )
        mock_response = mocked_auto_processed_claim_response(200, "Direct Deposit", 50)
        # When
        with patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            # Given
            messages = automated_reimbursement_request_service.submit_auto_processed_request_to_alegeus(
                reimbursement_request=given_reimbursement_request,
                wallet=wallet,
                cost_breakdown=cost_breakdown,
                reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
            )
            assert len(messages) == 2
            assert mock_send_event.call_count == 1
            assert mock_request.call_count == expected_requests_to_alegeus
            assert (
                len(given_reimbursement_request.claims) == expected_requests_to_alegeus
            )

    def test_submit_auto_processed_request_to_alegeus_dtr_claim_exists(
        self,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet,
        rr_cost_breakdown_data,
        individual_member_health_plan,
        mocked_auto_processed_claim_response,
        wallet_users,
    ):
        # Given (DTR exists but is missing the HRA)
        given_reimbursement_request = rx_reimbursement_request
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            False
        )
        individual_member_health_plan.employer_health_plan.is_hdhp = True

        mock_response = Response()
        mock_response.status_code = 200
        mock_response.json = lambda: [
            {
                "Status": "Approved",
                "StatusCode": 2,
                "TrackingNumber": "123abc",
                "AcctTypeCode": "DTR",
            },
        ]
        # DTR exists but HRA does not
        ReimbursementClaimFactory.create(
            alegeus_claim_id="123abc",
            alegeus_claim_key=1,
            status="APPROVED",
            reimbursement_request=given_reimbursement_request,
            amount=3000,
        )
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=3000,
            total_employer_responsibility=2000,
            reimbursement_request=given_reimbursement_request,
            deductible=3000,
        )
        mock_submit_claim_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", 50
        )
        # When
        with patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_submit_claim_request, patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            mock_submit_claim_request.return_value = mock_submit_claim_response
            # Given
            messages = automated_reimbursement_request_service.submit_auto_processed_request_to_alegeus(
                reimbursement_request=given_reimbursement_request,
                wallet=wallet,
                cost_breakdown=cost_breakdown,
                reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
            )
            assert len(messages) == 1
            assert mock_send_event.call_count == 1
            assert mock_request.call_count == 1
            assert mock_submit_claim_request.call_count == 1
            assert len(rx_reimbursement_request.claims) == 2

    def test_submit_auto_processed_request_to_alegeus_only_dtr_claim(
        self,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet,
        rr_cost_breakdown_data,
        individual_member_health_plan,
        mocked_auto_processed_claim_response,
        wallet_users,
    ):
        # Given (Only member responsibility - no hra claim)
        given_reimbursement_request = rx_reimbursement_request
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            False
        )
        individual_member_health_plan.employer_health_plan.is_hdhp = True

        mock_response = Response()
        mock_response.status_code = 200
        mock_response.json = lambda: [
            {
                "Status": "Denied",
                "StatusCode": 2,
                "TrackingNumber": "123abc",
                "AcctTypeCode": "DTR",
                "Amount": "50.00",
            },
        ]
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=5000,
            total_employer_responsibility=0,
            reimbursement_request=given_reimbursement_request,
            deductible=5000,
        )
        mock_submit_claim_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", 50
        )
        # When
        with patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_submit_claim_request, patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            mock_submit_claim_request.return_value = mock_submit_claim_response
            # Given
            messages = automated_reimbursement_request_service.submit_auto_processed_request_to_alegeus(
                reimbursement_request=given_reimbursement_request,
                wallet=wallet,
                cost_breakdown=cost_breakdown,
                reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
            )
            assert len(messages) == 2
            assert mock_send_event.call_count == 1
            assert mock_request.call_count == 0
            assert mock_submit_claim_request.call_count == 1
            assert len(rx_reimbursement_request.claims) == 1

    def test_submit_auto_processed_request_to_alegeus_no_dtr_hra_exists(
        self,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet,
        rr_cost_breakdown_data,
        individual_member_health_plan,
        mocked_auto_processed_claim_response,
        wallet_users,
    ):
        # Given (No DTR only HRA but it already exists here)
        given_reimbursement_request = rx_reimbursement_request
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            True
        )

        mock_response = Response()
        mock_response.status_code = 200
        mock_response.json = lambda: [
            {
                "Status": "Approved",
                "StatusCode": 2,
                "TrackingNumber": "123abc",
                "AcctTypeCode": "HRA",
                "Amount": "50.00",
            },
        ]
        # HRA exists
        ReimbursementClaimFactory.create(
            alegeus_claim_id="123abc",
            alegeus_claim_key=1,
            status="APPROVED",
            reimbursement_request=given_reimbursement_request,
            amount=50,
        )
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=0,
            total_employer_responsibility=5000,
            reimbursement_request=given_reimbursement_request,
            deductible=0,
        )
        mock_submit_claim_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", 50
        )
        # When
        with patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_submit_claim_request, patch(
            "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            mock_submit_claim_request.return_value = mock_submit_claim_response
            # Given
            messages = automated_reimbursement_request_service.submit_auto_processed_request_to_alegeus(
                reimbursement_request=given_reimbursement_request,
                wallet=wallet,
                cost_breakdown=cost_breakdown,
                reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
            )
            assert len(messages) == 2
            assert mock_send_event.call_count == 1
            assert mock_request.call_count == 1
            assert mock_submit_claim_request.call_count == 0
            assert len(rx_reimbursement_request.claims) == 1

    @pytest.mark.parametrize(
        "deductible_acc_enabled,is_hdhp,expected_requests_to_alegeus",
        [
            # HRA and DTR
            (False, True, 2),
            # Only HRA
            (True, False, 1),
            # Only HRA
            (False, False, 1),
        ],
    )
    def test__submit_auto_processed_claims_to_alegeus(
        self,
        deductible_acc_enabled,
        is_hdhp,
        expected_requests_to_alegeus,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet,
        rr_cost_breakdown_data,
        mocked_auto_processed_claim_response,
        individual_member_health_plan,
        wallet_users,
    ):
        # Given
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            deductible_acc_enabled
        )
        individual_member_health_plan.employer_health_plan.is_hdhp = is_hdhp
        given_reimbursement_request = rx_reimbursement_request
        given_reimbursement_request.state = ReimbursementRequestState.APPROVED
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=3500,
            total_employer_responsibility=1500,
            reimbursement_request=given_reimbursement_request,
            deductible=3000,
        )
        mock_response = mocked_auto_processed_claim_response(200, "Direct Deposit", 50)
        # When
        with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
            mock_request.return_value = mock_response
            # Given
            automated_reimbursement_request_service._submit_auto_processed_claims_to_alegeus(
                reimbursement_request=given_reimbursement_request,
                cost_breakdown=cost_breakdown,
                reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
            )
            assert mock_request.call_count == expected_requests_to_alegeus
            assert (
                len(given_reimbursement_request.claims) == expected_requests_to_alegeus
            )

    def test__submit_auto_processed_claims_to_alegeus_exception(
        self,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet,
        rr_cost_breakdown_data,
        mocked_auto_processed_claim_response,
        individual_member_health_plan,
        wallet_users,
    ):
        # Given
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            False
        )
        individual_member_health_plan.employer_health_plan.is_hdhp = True
        given_reimbursement_request = rx_reimbursement_request
        given_reimbursement_request.state = ReimbursementRequestState.APPROVED
        cost_breakdown = rr_cost_breakdown_data(
            total_member_responsibility=3500,
            total_employer_responsibility=1500,
            reimbursement_request=given_reimbursement_request,
            deductible=3000,
        )
        mock_response_one = mocked_auto_processed_claim_response(
            200, "Direct Deposit", 50
        )
        mock_response_two = mocked_auto_processed_claim_response(
            500, "Direct Deposit", 50
        )
        # When
        with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
            mock_request.side_effect = [mock_response_one, mock_response_two]
            # Given
            with pytest.raises(CreateDirectPaymentClaimErrorResponseException):
                automated_reimbursement_request_service._submit_auto_processed_claims_to_alegeus(
                    reimbursement_request=given_reimbursement_request,
                    cost_breakdown=cost_breakdown,
                    reimbursement_method=ReimbursementMethod.DIRECT_DEPOSIT,
                )
            assert mock_request.call_count == 2
            assert len(given_reimbursement_request.claims) == 1

    @pytest.mark.parametrize(
        "auto_processed",
        [True, False],
    )
    def test_check_for_duplicate_automated_rx_reimbursement(
        self,
        automated_reimbursement_request_service,
        wallet,
        pharmacy_prescription_repository,
        auto_processed,
    ):
        # Given
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        auto_processed_filtered = (
            None if auto_processed else ReimbursementRequestAutoProcessing.RX
        )
        dup_manual_rr = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category_association.reimbursement_request_category,
            state=ReimbursementRequestState.REIMBURSED,
            amount=422,
            person_receiving_service=wallet.member.full_name,
            person_receiving_service_id=wallet.user_id,
            service_provider="SMP Pharmacy",
            service_start_date=datetime.utcnow() - timedelta(days=25),
        )
        # Other RR that shouldn't be found
        ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category_association.reimbursement_request_category,
            state=ReimbursementRequestState.REIMBURSED,
            amount=422,
            person_receiving_service=wallet.member.full_name,
            person_receiving_service_id=wallet.user_id,
            service_provider="Other Pharmacy",
            service_start_date=datetime.utcnow() - timedelta(days=25),
        )
        dup_auto_processed_rr = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category_association.reimbursement_request_category,
            state=ReimbursementRequestState.APPROVED,
            amount=299,
            person_receiving_service=wallet.member.full_name,
            person_receiving_service_id=wallet.user_id,
            service_provider="SMP Pharmacy",
            auto_processed=ReimbursementRequestAutoProcessing.RX,
            service_start_date=datetime.utcnow() - timedelta(days=36),
        )
        prescription = PharmacyPrescriptionFactory(
            reimbursement_request_id=dup_auto_processed_rr.id,
            user_id=wallet.user_id,
            ndc_number="44087-1150-01",
            amount_owed=2.99,
            rx_unique_id="abc123",
        )
        pharmacy_prescription_repository.create(instance=prescription)

        given_reimbursement = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category_association.reimbursement_request_category,
            state=ReimbursementRequestState.NEW,
            amount=899,
            person_receiving_service=wallet.member.full_name,
            person_receiving_service_id=wallet.user_id,
            service_provider="SMP Pharmacy",
            service_start_date=datetime.utcnow(),
        )
        expected_rr_id = (
            dup_manual_rr.id if auto_processed else dup_auto_processed_rr.id
        )

        # When
        duplicates = automated_reimbursement_request_service.check_for_duplicate_automated_rx_reimbursement(
            reimbursement_request=given_reimbursement,
            auto_processed=auto_processed_filtered,
        )
        assert duplicates == [expected_rr_id]

    def test_reset_reimbursement_request_with_cost_breakdown(
        self,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet,
        rr_cost_breakdown_data,
    ):
        # Given
        given_original_amount = 7777
        given_reimbursement_request = rx_reimbursement_request
        given_cost_breakdown = CostBreakdownFactory.create(
            wallet_id=given_reimbursement_request.reimbursement_wallet_id,
            reimbursement_request_id=given_reimbursement_request.id,
        )
        # When
        automated_reimbursement_request_service.reset_reimbursement_request(
            original_amount=given_original_amount,
            reimbursement_request=given_reimbursement_request,
            cost_breakdown=given_cost_breakdown,
        )
        found_reimbursement_request = ReimbursementRequest.query.get(
            given_reimbursement_request.id
        )
        found_cost_breakdown = CostBreakdown.query.get(given_cost_breakdown.id)
        # Then
        assert found_cost_breakdown is None
        assert found_reimbursement_request.amount == given_original_amount

    def test_reset_reimbursement_request_no_cost_breakdown(
        self,
        automated_reimbursement_request_service,
        rx_reimbursement_request,
        wallet,
    ):
        # Given
        given_original_amount = 7777
        given_reimbursement_request = rx_reimbursement_request
        # When
        automated_reimbursement_request_service.reset_reimbursement_request(
            original_amount=given_original_amount,
            reimbursement_request=given_reimbursement_request,
            cost_breakdown=None,
        )
        found_reimbursement_request = ReimbursementRequest.query.get(
            given_reimbursement_request.id
        )
        # Then
        assert found_reimbursement_request.amount == given_original_amount
