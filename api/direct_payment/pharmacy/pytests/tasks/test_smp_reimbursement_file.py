import datetime
from unittest.mock import patch

import pytest as pytest
from freezegun import freeze_time

from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import AmountType, CostBreakdownType
from cost_breakdown.models.cost_breakdown import CostBreakdown, CostBreakdownData
from cost_breakdown.pytests.factories import CostBreakdownFactory, RTETransactionFactory
from direct_payment.clinic.pytests.factories import (
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
)
from direct_payment.pharmacy.constants import SMP_FERTILITY_CLINIC_1
from direct_payment.pharmacy.tasks.libs.smp_reimbursement_file import (
    ReimbursementFileProcessor,
)
from payer_accumulator.common import PayerName
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import PayerFactory
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.factories import ReimbursementWalletUsersFactory
from wallet.models.constants import (
    CostSharingCategory,
    CostSharingType,
    CoverageType,
    FamilyPlanType,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.factories import (
    EmployerHealthPlanCoverageFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementRequestFactory,
)
from wallet.repository.member_benefit import MemberBenefitRepository


@pytest.fixture
def user_member_benefit(wallet):
    rwu = ReimbursementWalletUsersFactory.create(
        user_id=wallet.user_id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )
    benefit_repo = MemberBenefitRepository()
    member_benefit = benefit_repo.get_by_user_id(rwu.user_id)
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            percent=0.05,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COPAY,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            absolute_amount=2000,
        ),
    ]
    employer_health_plan = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        cost_sharings=cost_sharing,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
                max_oop_per_covered_individual=200,
            ),
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
            ),
            EmployerHealthPlanCoverageFactory.create(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
                plan_type=FamilyPlanType.FAMILY,
                max_oop_per_covered_individual=200,
            ),
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
                plan_type=FamilyPlanType.FAMILY,
            ),
        ],
    )
    MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        is_subscriber=True,
        member_id=wallet.user_id,
        reimbursement_wallet=wallet,
    )
    PayerFactory.create(id=1, payer_name=PayerName.UHC, payer_code="uhc_code")
    return member_benefit.benefit_id


@pytest.fixture
def processor():
    return ReimbursementFileProcessor()


@pytest.fixture
def mock_procedure():
    return GlobalProcedureFactory.create(
        id=1,
        type="pharmacy",
    )


class TestSMPReimbursementFile:
    def test_process_reimbursement_success(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mocked_auto_processed_claim_response,
        expense_subtypes,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        given_paid_amount = "48.00"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit,
            filled_date=datetime.datetime.utcnow().date().strftime("%m/%d/%Y"),
            amount_paid=given_paid_amount,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_procedure = GlobalProcedureFactory.create(id=1, type="pharmacy")
        given_rx_unique_id = "7065817-12"
        mock_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", given_paid_amount
        )
        mock_rx_received_date_from_file = datetime.datetime(2023, 8, 1)
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure],
        ), patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
            # Then
            assert processor.failed_rows == []
            assert prescription.reimbursement_request_id
            assert prescription.user_id == wallet.user_id
            # Below shows the rx received date from the mock file is what is set for start/end date
            assert (
                reimbursement_request.service_start_date
                == mock_rx_received_date_from_file
            )
            assert (
                reimbursement_request.service_end_date
                == mock_rx_received_date_from_file
            )
            assert mock_send_event.called
            assert (
                mock_send_event.call_args.kwargs["data"]["events"][0]["name"]
                == "wallet_reimbursement_state_rx_auto_approved"
            )
            assert mock_request.call_count == 1

            cost_breakdown = CostBreakdown.query.filter_by(
                reimbursement_request_id=prescription.reimbursement_request_id
            )
            assert cost_breakdown

            # Accumulation mapping row not created because member responsibility is 0
            accumulation_mapping = AccumulationTreatmentMapping.query.filter_by(
                reimbursement_request_id=prescription.reimbursement_request_id
            ).first()
            assert accumulation_mapping is None

    def test_process_reimbursement_run_out_wallet_success(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mocked_auto_processed_claim_response,
        mock_procedure,
        expense_subtypes,
    ):
        # Given

        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        wallet.state = WalletState.RUNOUT
        mock_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", 48.15
        )
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit,
            filled_date=datetime.datetime.utcnow().date().strftime("%m/%d/%Y"),
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_rx_unique_id = "7065817-12"
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            # Then
            assert processor.failed_rows == []
            assert prescription.reimbursement_request_id
            assert prescription.user_id == wallet.user_id
            assert mock_send_event.called
            assert (
                mock_send_event.call_args.kwargs["data"]["events"][0]["name"]
                == "wallet_reimbursement_state_rx_auto_approved"
            )
            assert mock_request.call_count == 1

    def test_process_reimbursement_dry_run(
        self, wallet, smp_reimbursement_file, pharmacy_prescription_service, processor
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        processor = ReimbursementFileProcessor(dry_run=True)
        # When
        processor.process_file(smp_reimbursement_file())
        prescription = (
            pharmacy_prescription_service.get_prescription_by_unique_id_status(
                rx_unique_id=given_rx_unique_id
            )
        )
        # Then
        assert prescription is None

    def test_process_reimbursement_fails_file_validation(
        self, smp_reimbursement_file, processor
    ):
        # Given/Whe
        processor.process_file(smp_reimbursement_file(benefit_id=""))
        # Then
        assert processor.failed_rows == [
            ("", "7065817-12", "Missing required data in record.")
        ]

    def test_process_reimbursement_failed_fetching_wallet_expense_subtype(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mocked_auto_processed_claim_response,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        given_paid_amount = "48.00"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit,
            filled_date=datetime.datetime.utcnow().date().strftime("%m/%d/%Y"),
            amount_paid=given_paid_amount,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_procedure = GlobalProcedureFactory.create(id=1, type="pharmacy")
        mock_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", given_paid_amount
        )
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure],
        ), patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ):
            mock_request.return_value = mock_response
            # When
            processor.process_file(given_reimbursement_file)

        # Then
        assert processor.failed_rows == [
            (user_member_benefit, "7065817-12", "Could not find wallet expense subtype")
        ]

    @pytest.mark.parametrize(
        argnames="wallet_state",
        argvalues=(WalletState.PENDING, WalletState.DISQUALIFIED, WalletState.EXPIRED),
    )
    def test_process_reimbursement_fails_invalid_wallet_state(
        self,
        wallet,
        smp_reimbursement_file,
        pharmacy_prescription_service,
        processor,
        user_member_benefit,
        wallet_state,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        wallet.state = wallet_state
        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ):
            processor.process_file(
                smp_reimbursement_file(benefit_id=user_member_benefit)
            )
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )

        # Then
        assert prescription.rx_unique_id == given_rx_unique_id
        assert processor.failed_rows == [
            (
                user_member_benefit,
                "7065817-12",
                "Wallet not found.",
            )
        ]

    def test_process_reimbursement_fails_invalid_user(
        self,
        wallet,
        smp_reimbursement_file,
        pharmacy_prescription_service,
        processor,
        mock_procedure,
        expense_subtypes,
        user_member_benefit,
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit, first_name="Bad Data"
        )
        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ):
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
        # Then
        assert prescription.rx_unique_id == given_rx_unique_id
        assert reimbursement_request
        assert reimbursement_request.state == ReimbursementRequestState.DENIED
        assert prescription.user_id is None
        assert processor.failed_rows == [
            (user_member_benefit, "7065817-12", "User not found.")
        ]

    def test_process_reimbursement_fails_invalid_patient_name(
        self,
        wallet,
        smp_reimbursement_file,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit, first_name="Unknown"
        )
        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch("utils.braze_events.braze.send_event") as mock_send_event:
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
        # Then
        assert prescription.rx_unique_id == given_rx_unique_id
        assert reimbursement_request
        assert reimbursement_request.state == ReimbursementRequestState.DENIED
        assert prescription.user_id is None
        assert processor.failed_rows == [
            (user_member_benefit, "7065817-12", "User not found.")
        ]
        assert mock_send_event.called
        assert (
            mock_send_event.call_args.kwargs["event_name"]
            == "wallet_reimbursement_state_declined_erisa"
        )

    @pytest.mark.parametrize(
        argnames="wallet_state,rx_enabled,country_code,direct_payment_enabled",
        argvalues=(
            # not qualified, rx_enabled = False, country_code = "US", direct_payment_enabled
            (WalletState.QUALIFIED, False, "US", False),
            # qualified, rx_enabled = True, country_code = "US"
            (WalletState.QUALIFIED, True, "US", True),
            # qualified, rx_enabled, country_code = "SE"
            (WalletState.QUALIFIED, False, "SE", True),
        ),
    )
    def test_process_reimbursement_fails_config_check(
        self,
        wallet,
        smp_reimbursement_file,
        wallet_state,
        rx_enabled,
        country_code,
        direct_payment_enabled,
        pharmacy_prescription_service,
        processor,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        rwu = ReimbursementWalletUsersFactory.create(
            user_id=wallet.user_id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = (
            rx_enabled
        )
        wallet.reimbursement_organization_settings.direct_payment_enabled = (
            direct_payment_enabled
        )
        wallet.state = wallet_state
        rwu.member.member_profile.country_code = country_code

        benefit_repo = MemberBenefitRepository()
        member_benefit = benefit_repo.get_by_user_id(rwu.user_id)
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=member_benefit.benefit_id
        )
        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch("utils.braze_events.braze.send_event") as mock_send_event:
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
        # Then
        assert reimbursement_request
        assert reimbursement_request.state == ReimbursementRequestState.DENIED
        assert prescription.user_id
        assert processor.failed_rows == [
            (member_benefit.benefit_id, "7065817-12", "Problem with configurations.")
        ]
        assert mock_send_event.called

    def test_process_reimbursement_no_fertility_clinic(
        self,
        wallet,
        smp_reimbursement_file,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mock_procedure,
        mocked_auto_processed_claim_response,
        expense_subtypes,
    ):
        # Given
        mock_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", 5000
        )
        given_rx_unique_id = "7065817-12"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        FertilityClinicFactory.create(name="unknown")
        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
        # Then
        assert prescription.rx_unique_id == given_rx_unique_id
        assert reimbursement_request
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED
        assert prescription.user_id
        assert mock_send_event.called

    def test_process_reimbursement_no_global_procedure(
        self,
        wallet,
        smp_reimbursement_file,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)
        given_procedure_bad_type = GlobalProcedureFactory.create(
            id=1, name="Test", type="medical"
        )

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure_bad_type],
        ), patch("utils.braze_events.braze.send_event") as mock_send_event:
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
            # Then
            assert prescription.rx_unique_id == given_rx_unique_id
            assert reimbursement_request is None
            assert processor.failed_rows == [
                (user_member_benefit, "7065817-12", "Global Procedure not found.")
            ]
            assert mock_send_event.call_count == 0

    def test_process_reimbursement_fails_no_cost_share_category(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        expense_subtypes,
    ):
        # Given
        mock_procedure = GlobalProcedureFactory.create(
            id=1, type="pharmacy", cost_sharing_category=None
        )

        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_rx_unique_id = "7065817-12"

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch("utils.braze_events.braze.send_event") as mock_send_event:
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
            # Then
            assert prescription.rx_unique_id == given_rx_unique_id
            assert reimbursement_request
            assert reimbursement_request.state == ReimbursementRequestState.DENIED
            assert prescription.user_id
            assert processor.failed_rows == [
                (
                    user_member_benefit,
                    "7065817-12",
                    "Cost Sharing Category not found.",
                )
            ]
            assert mock_send_event.called
            assert (
                mock_send_event.call_args.kwargs["event_name"]
                == "wallet_reimbursement_state_declined_erisa"
            )

    def test_process_reimbursement_fails_no_category(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        request_category = category_association.reimbursement_request_category
        request_category.reimbursement_plan = None

        given_rx_unique_id = "7065817-12"

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch("utils.braze_events.braze.send_event") as mock_send_event:
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
            # Then
            assert prescription.rx_unique_id == given_rx_unique_id
            assert reimbursement_request
            assert reimbursement_request.state == ReimbursementRequestState.DENIED
            assert prescription.user_id
            assert processor.failed_rows == [
                (
                    user_member_benefit,
                    "7065817-12",
                    "Reimbursement Category not found.",
                )
            ]
            assert mock_send_event.called
            assert (
                mock_send_event.call_args.kwargs["event_name"]
                == "wallet_reimbursement_state_declined_erisa"
            )

    def test_process_reimbursement_fails_no_cost_breakdown(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            True
        )

        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_rx_unique_id = "7065817-12"

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
            return_value=None,
        ):
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
            # Then
            assert prescription.rx_unique_id == given_rx_unique_id
            assert reimbursement_request
            assert reimbursement_request.state == ReimbursementRequestState.NEW
            assert prescription.user_id
            assert processor.failed_rows == [
                (
                    user_member_benefit,
                    "7065817-12",
                    "Error running Cost Breakdown.",
                )
            ]

    def test_process_reimbursement_fails_alegeus(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mocked_auto_processed_claim_response,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_rx_unique_id = "7065817-12"

        given_cost_breakdown = CostBreakdownFactory.create(
            wallet_id=wallet.id,
            total_member_responsibility=3000,
            total_employer_responsibility=1515,
        )

        mock_response = mocked_auto_processed_claim_response(500, "Direct Deposit", 50)
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor"
            ".get_cost_breakdown_for_reimbursement_request"
        ) as cb, patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request:

            cb.return_value = given_cost_breakdown
            mock_request.return_value = mock_response
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
            # Then
            assert prescription.rx_unique_id == given_rx_unique_id
            assert reimbursement_request
            assert reimbursement_request.state == ReimbursementRequestState.NEW
            assert reimbursement_request.amount == 4815
            assert prescription.user_id
            assert processor.failed_rows == [
                (
                    user_member_benefit,
                    "7065817-12",
                    "Failed to submit auto processed claim to Alegeus.",
                )
            ]
            cost_breakdown = CostBreakdown.query.filter_by(
                reimbursement_request_id=prescription.reimbursement_request_id
            ).first()
            assert cost_breakdown is None

    def test_process_reimbursement_fails_no_wallet_balance(
        self,
        wallet,
        smp_reimbursement_file,
        pharmacy_prescription_service,
        processor,
        user_member_benefit,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        amount = category_association.reimbursement_request_category_maximum
        ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category_association.reimbursement_request_category,
            state=ReimbursementRequestState.APPROVED,
            amount=amount,
        )
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit,
            filled_date=datetime.datetime.utcnow().date().strftime("%m/%d/%Y"),
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_rx_unique_id = "7065817-12"
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch("utils.braze_events.braze.send_event") as mock_send_event:
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            # Then
            assert prescription.reimbursement_request_id
            assert prescription.user_id == wallet.user_id
            assert processor.failed_rows == [
                (
                    user_member_benefit,
                    "7065817-12",
                    "No wallet balance remaining.",
                )
            ]
            assert mock_send_event.called
            assert (
                mock_send_event.call_args.kwargs["event_name"]
                == "wallet_reimbursement_state_declined_erisa"
            )

    @pytest.mark.parametrize("da_enabled, accumulations", [(True, 1), (False, 0)])
    def test_process_reimbursement_member_responsibility_accumulates(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mocked_auto_processed_claim_response,
        da_enabled,
        accumulations,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            da_enabled
        )
        given_paid_amount = "48.00"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit,
            filled_date=datetime.datetime.utcnow().date().strftime("%m/%d/%Y"),
            amount_paid=given_paid_amount,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_rx_unique_id = "7065817-12"
        mock_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", given_paid_amount
        )
        RTETransactionFactory.create(id=123456789)
        mock_cost_breakdown = CostBreakdownData(
            rte_transaction_id=123456789,
            total_member_responsibility=10,
            deductible=10,
            oop_applied=0,
            total_employer_responsibility=38,
            beginning_wallet_balance=100,
            ending_wallet_balance=62,
            cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
            amount_type=AmountType.INDIVIDUAL,
        )
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event, patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._run_data_service",
            return_value=mock_cost_breakdown,
        ):
            mock_request.return_value = mock_response
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            # Then
            assert processor.failed_rows == []
            assert mock_send_event.called
            assert (
                mock_send_event.call_args.kwargs["data"]["events"][0]["name"]
                == "wallet_reimbursement_state_rx_auto_approved"
            )

            # Accumulation mapping row created because member responsibility is more than 0
            accumulation_mapping = AccumulationTreatmentMapping.query.filter_by(
                reimbursement_request_id=prescription.reimbursement_request_id
            ).all()
            assert len(accumulation_mapping) == accumulations

    def test_duplicate_reimbursement_detected(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        pharmacy_prescription_repository,
        user_member_benefit,
        processor,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        given_paid_amount = "48.00"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit,
            rx_received_date=datetime.datetime.utcnow().date().strftime("%m/%d/%Y"),
            amount_paid=given_paid_amount,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_rx_unique_id = "7065817-12"

        # Duplicate Reimbursement not from SMP
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category_association.reimbursement_request_category,
            state=ReimbursementRequestState.APPROVED,
            amount=given_paid_amount,
            person_receiving_service=wallet.member.full_name,
            person_receiving_service_id=wallet.user_id,
            service_provider="SMP Pharmacy",
        )
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ):
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            # Then
            assert processor.failed_rows == [
                (
                    user_member_benefit,
                    "7065817-12",
                    "Duplicate Reimbursement Request found.",
                )
            ]
            assert prescription.reimbursement_request_id
            assert prescription.user_id == wallet.user_id

            rr = ReimbursementRequest.query.get(prescription.reimbursement_request_id)
            assert rr.state == ReimbursementRequestState.NEW

            # Accumulation mapping row not created because member responsibility is 0
            accumulation_mapping = AccumulationTreatmentMapping.query.filter_by(
                reimbursement_request_id=prescription.reimbursement_request_id
            ).first()
            assert accumulation_mapping is None

    def test_duplicate_after_process_reimbursement_success(
        self,
        smp_reimbursement_file,
        wallet,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mocked_auto_processed_claim_response,
        mock_procedure,
        expense_subtypes,
    ):
        # Given
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        given_paid_amount = "48.00"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit,
            rx_received_date=datetime.datetime.utcnow().date().strftime("%m/%d/%Y"),
            amount_paid=given_paid_amount,
        )
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        given_rx_unique_id = "7065817-12"
        mock_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", given_paid_amount
        )
        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[mock_procedure],
        ), patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request, patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            # Then
            assert processor.failed_rows == []
            assert prescription.reimbursement_request_id
            assert prescription.user_id == wallet.user_id
            assert mock_request.call_count == 1
            assert mock_send_event.called
            assert (
                mock_send_event.call_args.kwargs["data"]["events"][0]["name"]
                == "wallet_reimbursement_state_rx_auto_approved"
            )

            rr = ReimbursementRequest.query.get(prescription.reimbursement_request_id)
            assert rr.state == ReimbursementRequestState.APPROVED

            # Ensure running process file twice doesn't create new table rows
            all_rrs = ReimbursementRequest.query.all()
            all_prescriptions = (
                pharmacy_prescription_service.get_by_reimbursement_request_ids(
                    reimbursement_request_ids=[rr.id for rr in all_rrs]
                )
            )
            assert len(all_rrs) == 1
            assert len(all_prescriptions) == 1

            processor.process_file(given_reimbursement_file)

            all_rrs = ReimbursementRequest.query.all()
            all_prescriptions = (
                pharmacy_prescription_service.get_by_reimbursement_request_ids(
                    reimbursement_request_ids=[rr.id for rr in all_rrs]
                )
            )
            assert len(all_rrs) == 1
            assert len(all_prescriptions) == 1

            assert all_rrs[0].wallet_expense_subtype == expense_subtypes["FERTRX"]
            assert (
                all_rrs[0].original_wallet_expense_subtype == expense_subtypes["FERTRX"]
            )

    def test_process_reimbursement_fails_no_effective_global_procedure(
        self,
        wallet,
        smp_reimbursement_file,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit, rx_received_date="08/01/2023"
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[],
        ), patch("utils.braze_events.braze.send_event") as mock_send_event:
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
            # Then
            assert prescription.rx_unique_id == given_rx_unique_id
            assert reimbursement_request is None
            assert processor.failed_rows == [
                (user_member_benefit, "7065817-12", "Global Procedure not found.")
            ]
            assert mock_send_event.call_count == 0

    def test_process_reimbursement_success_effective_global_procedure(
        self,
        wallet,
        smp_reimbursement_file,
        pharmacy_prescription_service,
        user_member_benefit,
        processor,
        mocked_auto_processed_claim_response,
        expense_subtypes,
    ):
        # Given
        given_rx_unique_id = "7065817-12"
        given_paid_amount = "48.00"
        given_reimbursement_file = smp_reimbursement_file(
            benefit_id=user_member_benefit, rx_received_date="08/01/2024"
        )
        wallet.reimbursement_organization_settings.rx_direct_payment_enabled = False
        fertility_clinic = FertilityClinicFactory.create(name=SMP_FERTILITY_CLINIC_1)
        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)
        given_procedure_effective = GlobalProcedureFactory.create(
            id=1,
            name="Test",
            type="pharmacy",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2025, 12, 31),
        )

        FertilityClinicLocationFactory.create(fertility_clinic=fertility_clinic)
        mock_response = mocked_auto_processed_claim_response(
            200, "Direct Deposit", given_paid_amount
        )

        with patch.object(
            ProcedureService,
            "get_procedures_by_ndc_numbers",
            return_value=[given_procedure_effective],
        ), patch(
            "wallet.alegeus_api.AlegeusApi.make_api_request"
        ) as mock_request, patch(
            "utils.braze_events.braze.send_event"
        ) as mock_send_event:
            mock_request.return_value = mock_response
            # When
            processor.process_file(given_reimbursement_file)
            prescription = (
                pharmacy_prescription_service.get_prescription_by_unique_id_status(
                    rx_unique_id=given_rx_unique_id
                )
            )
            reimbursement_request = ReimbursementRequest.query.get(
                prescription.reimbursement_request_id
            )
            # Then
            assert prescription.rx_unique_id == given_rx_unique_id
            assert processor.failed_rows == []
            assert prescription.reimbursement_request_id
            assert prescription.user_id == wallet.user_id
            assert mock_request.called
            assert reimbursement_request.state == ReimbursementRequestState.APPROVED
            assert mock_send_event.call_count == 0

    @freeze_time("2024-01-01 12:00:00")
    def test_get_next_rx_timestamp(self, processor):
        # Same RX date should increment
        assert processor.get_next_rx_timestamp("01/01/2024") == datetime.datetime(
            2024, 1, 1
        )
        assert processor.get_next_rx_timestamp("01/01/2024") == datetime.datetime(
            2024, 1, 1, 0, 0, 1
        )
        assert processor.get_next_rx_timestamp("01/01/2024") == datetime.datetime(
            2024, 1, 1, 0, 0, 2
        )

        # Different RX date should start fresh
        assert processor.get_next_rx_timestamp("01/02/2024") == datetime.datetime(
            2024, 1, 2
        )
        assert processor.get_next_rx_timestamp("01/02/2024") == datetime.datetime(
            2024, 1, 2, 0, 0, 1
        )

    @freeze_time("2024-01-01 12:00:00")
    def test_create_reimbursement_request_params(self, processor):
        # Given
        row = {
            "Rx Received Date": "01/01/2024",
            "Drug Name": "Test Drug",
        }
        # When
        params1 = processor._create_reimbursement_request_params(
            row=row,
            clinic_name="Test Clinic",
            cost=1000,
            state=ReimbursementRequestState.NEW,
        )
        params2 = processor._create_reimbursement_request_params(
            row=row,
            clinic_name="Test Clinic",
            cost=1000,
            state=ReimbursementRequestState.NEW,
        )

        # Then
        assert params1.service_start_date == datetime.datetime(2024, 1, 1)
        assert params1.service_end_date == datetime.datetime(2024, 1, 1)
        assert params2.service_start_date == datetime.datetime(2024, 1, 1, 0, 0, 1)
        assert params2.service_end_date == datetime.datetime(2024, 1, 1, 0, 0, 1)
