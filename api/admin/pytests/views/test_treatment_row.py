import uuid
from unittest.mock import patch

import pytest

from admin.views.models.payer_accumulator import TreatmentRow
from cost_breakdown.constants import AmountType, ClaimType, CostBreakdownType
from cost_breakdown.cost_breakdown_processor import CostBreakdownProcessor
from cost_breakdown.models.cost_breakdown import CostBreakdown, CostBreakdownData
from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    ReimbursementRequestToCostBreakdownFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.common import PayerName
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import PayerReportStatus
from payer_accumulator.pytests.factories import (
    PayerAccumulationReportsFactory,
    PayerFactory,
)
from utils.payments import convert_cents_to_dollars
from wallet.models.constants import (
    CostSharingCategory,
    CostSharingType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementRequestFactory,
)
from wallet.pytests.fixtures import WalletTestHelper


@pytest.fixture(scope="function")
def employer_health_plan_cost_sharing():
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
    return cost_sharing


@pytest.fixture(scope="function")
def test_payer():
    return PayerFactory.create(payer_name=PayerName.Cigna, payer_code="00192")


@pytest.fixture(scope="function")
def treatment_row():
    return TreatmentRow(AccumulationTreatmentMapping)


@pytest.fixture
def cost_breakdown_processor():
    processor = CostBreakdownProcessor()
    return processor


@pytest.fixture(scope="function")
def payer_accumulation_report(test_payer):
    given_payer_accumulation_report = PayerAccumulationReportsFactory.create(
        payer_id=test_payer.id
    )
    return given_payer_accumulation_report


@pytest.fixture
def cigna_structured_detail_row():
    return {
        "member_pid": "U1234567801",
        "accumulation_counter": "0002",
        "accumulations": [
            {
                "accumulator_type": "D",
                "amount": "00000000{",
            },
            {
                "accumulator_type": "O",
                "amount": "0000050{",
            },
        ],
    }


@pytest.fixture
def accumulation_wallet(test_payer, employer_health_plan_cost_sharing):
    wallet_test_helper = WalletTestHelper()
    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={"direct_payment_enabled": True}
    )
    wallet_test_helper.add_lifetime_family_benefit(
        organization.reimbursement_organization_settings[0]
    )
    user = wallet_test_helper.create_user_for_organization(
        organization,
        member_profile_parameters={
            "country_code": "US",
            "subdivision_code": "US-NY",
        },
    )
    wallet = wallet_test_helper.create_pending_wallet(
        user,
        wallet_parameters={
            "primary_expense_type": ReimbursementRequestExpenseTypes.FERTILITY
        },
    )
    wallet_test_helper.qualify_wallet(wallet)

    ehp = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        benefits_payer_id=test_payer.id,
        cost_sharings=employer_health_plan_cost_sharing,
    )
    MemberHealthPlanFactory.create(
        employer_health_plan_id=ehp.id,
        employer_health_plan=ehp,
        reimbursement_wallet_id=wallet.id,
        reimbursement_wallet=wallet,
        member_id=wallet.member.id,
        patient_sex=MemberHealthPlanPatientSex.FEMALE,
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
        subscriber_insurance_id="U1234567801",
    )
    return wallet


@pytest.fixture(scope="function")
def reimbursement_request(accumulation_wallet):
    category = accumulation_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=accumulation_wallet,
        category=category,
        amount=22000,
        procedure_type=TreatmentProcedureType.MEDICAL.value,
        person_receiving_service_id=accumulation_wallet.user_id,
        cost_sharing_category=CostSharingCategory.MEDICAL_CARE.value,
    )
    return reimbursement_request


@pytest.fixture(scope="function")
def wallet_cycle_based(test_payer, employer_health_plan_cost_sharing):
    wallet_test_helper = WalletTestHelper()
    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={
            "direct_payment_enabled": True,
            "allowed_reimbursement_categories__cycle_based": True,
        }
    )
    wallet_test_helper.add_lifetime_family_benefit(
        organization.reimbursement_organization_settings[0]
    )
    user = wallet_test_helper.create_user_for_organization(
        organization,
        member_profile_parameters={
            "country_code": "US",
            "subdivision_code": "US-NY",
        },
    )
    wallet = wallet_test_helper.create_pending_wallet(
        user,
        wallet_parameters={
            "primary_expense_type": ReimbursementRequestExpenseTypes.FERTILITY
        },
    )
    wallet_test_helper.qualify_wallet(wallet)

    ehp = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        benefits_payer_id=test_payer.id,
        cost_sharings=employer_health_plan_cost_sharing,
    )
    MemberHealthPlanFactory.create(
        employer_health_plan_id=ehp.id,
        employer_health_plan=ehp,
        reimbursement_wallet_id=wallet.id,
        reimbursement_wallet=wallet,
        member_id=wallet.member.id,
        patient_sex=MemberHealthPlanPatientSex.FEMALE,
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
        subscriber_insurance_id="U1234567801",
    )
    return wallet


@pytest.fixture(scope="function")
def reimbursement_request_cycle(wallet_cycle_based):
    category = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=wallet_cycle_based,
        category=category,
        amount=22000,
        procedure_type=TreatmentProcedureType.MEDICAL.value,
        person_receiving_service_id=wallet_cycle_based.user_id,
        cost_sharing_category=CostSharingCategory.MEDICAL_CARE.value,
        cost_credit=1,
    )
    return reimbursement_request


@pytest.fixture
def accumulation_cost_breakdown_data():
    return CostBreakdownData(
        rte_transaction_id=None,
        total_member_responsibility=10000,
        total_employer_responsibility=200000,
        beginning_wallet_balance=250000,
        ending_wallet_balance=0,
        cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
        amount_type=AmountType.INDIVIDUAL,
        deductible=150,
        deductible_remaining=0,
        coinsurance=0,
        copay=0,
        overage_amount=0,
        oop_applied=200,
        oop_remaining=300,
        family_deductible_remaining=0,
        family_oop_remaining=0,
    )


@pytest.fixture
def form_data(test_payer):
    def data(reimbursement_request_id="", deductible_override="", oop_override=""):
        form_data = {
            "payer_id": test_payer.id,
            "filename": "test_file",
            "report_date": "2024-03-15",
            "status": PayerReportStatus.FAILURE.value,
            "treatment_mappings-0-id": "",
            "treatment_mappings-0-treatment_procedure_uuid": "",
            "treatment_mappings-0-reimbursement_request_id": reimbursement_request_id,
            "treatment_mappings-0-record_type": "MEDICAL",
            "treatment_mappings-0-out_of_pocket_override": oop_override,
            "treatment_mappings-0-deductible_override": deductible_override,
        }
        return form_data

    return data


class TestTreatmentRowReimbursementRequest:
    def test_reimbursement_request_runs_cost_breakdown(
        self,
        admin_client,
        test_payer,
        reimbursement_request,
        accumulation_cost_breakdown_data,
        payer_accumulation_report,
        cigna_structured_detail_row,
        form_data,
    ):
        # Given
        data = form_data(reimbursement_request.id)
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor"
            ".cost_breakdown_data_service_from_reimbursement_request",
        ) as cost_breakdown_data_service_from_reimbursement_request, patch(
            "payer_accumulator.accumulation_report_service.AccumulationReportService"
            ".regenerate_and_overwrite_report"
        ) as detail_view, patch(
            "maven.feature_flags.bool_variation", return_value=True
        ):
            detail_view.return_value = cigna_structured_detail_row
            cost_breakdown_data_service_from_reimbursement_request().get_cost_breakdown_data.return_value = (
                accumulation_cost_breakdown_data
            )
            # When
            res = admin_client.post(
                f"/admin/payeraccumulationreports/edit/?id={payer_accumulation_report.id}",
                data=data,
                headers={"Content-Type": "multipart/form-data"},
            )
            # Then
            reimbursement_request = ReimbursementRequest.query.get(
                reimbursement_request.id
            )
            cost_breakdown: CostBreakdown = (
                CostBreakdown.query.filter(
                    CostBreakdown.reimbursement_request_id == reimbursement_request.id
                )
            ).one()
            new_mapping: AccumulationTreatmentMapping = (
                AccumulationTreatmentMapping.query.filter(
                    AccumulationTreatmentMapping.reimbursement_request_id
                    == reimbursement_request.id
                ).one()
            )
            assert res.status_code == 302
            assert cost_breakdown.reimbursement_request_id == reimbursement_request.id
            assert new_mapping.payer_id == test_payer.id
            assert (
                reimbursement_request.amount
                == accumulation_cost_breakdown_data.total_employer_responsibility
            )
            assert detail_view.called
            assert (
                cost_breakdown_data_service_from_reimbursement_request.call_count == 2
            )

    def test_reimbursement_request_runs_cost_breakdown_cycle_wallet(
        self,
        admin_client,
        test_payer,
        reimbursement_request_cycle,
        accumulation_cost_breakdown_data,
        payer_accumulation_report,
        cigna_structured_detail_row,
        form_data,
    ):
        # Given
        given_original_rr_amount = reimbursement_request_cycle.amount
        data = form_data(reimbursement_request_cycle.id)
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor"
            ".cost_breakdown_data_service_from_reimbursement_request",
        ) as cost_breakdown_data_service_from_reimbursement_request, patch(
            "payer_accumulator.accumulation_report_service.AccumulationReportService"
            ".regenerate_and_overwrite_report"
        ) as detail_view, patch(
            "maven.feature_flags.bool_variation", return_value=True
        ):
            detail_view.return_value = cigna_structured_detail_row
            cost_breakdown_data_service_from_reimbursement_request().get_cost_breakdown_data.return_value = (
                accumulation_cost_breakdown_data
            )
            # When
            res = admin_client.post(
                f"/admin/payeraccumulationreports/edit/?id={payer_accumulation_report.id}",
                data=data,
                headers={"Content-Type": "multipart/form-data"},
            )
            # Then
            reimbursement_request = ReimbursementRequest.query.get(
                reimbursement_request_cycle.id
            )
            cost_breakdown: CostBreakdown = (
                CostBreakdown.query.filter(
                    CostBreakdown.reimbursement_request_id == reimbursement_request.id
                )
            ).one()
            new_mapping: AccumulationTreatmentMapping = (
                AccumulationTreatmentMapping.query.filter(
                    AccumulationTreatmentMapping.reimbursement_request_id
                    == reimbursement_request.id
                ).one()
            )
            assert res.status_code == 302
            assert cost_breakdown.reimbursement_request_id == reimbursement_request.id
            assert new_mapping.payer_id == test_payer.id
            assert (
                reimbursement_request.amount
                == accumulation_cost_breakdown_data.total_employer_responsibility
            )
            assert detail_view.called
            assert (
                cost_breakdown_data_service_from_reimbursement_request.call_count == 2
            )
            assert (
                cost_breakdown_data_service_from_reimbursement_request.call_args.kwargs
                == {
                    "reimbursement_request": reimbursement_request,
                    "user_id": reimbursement_request.person_receiving_service_id,
                    "cost_sharing_category": CostSharingCategory.MEDICAL_CARE.value,
                    "wallet_balance_override": given_original_rr_amount,
                    "tier": None,
                    "asof_date": reimbursement_request.service_start_date,
                }
            )

    def test_reimbursement_request_uses_overrides(
        self,
        admin_client,
        payer_accumulation_report,
        test_payer,
        reimbursement_request,
        accumulation_cost_breakdown_data,
        cigna_structured_detail_row,
        form_data,
    ):
        # Given
        data = form_data(
            reimbursement_request_id=reimbursement_request.id,
            deductible_override="300",
            oop_override="400",
        )
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor"
            ".cost_breakdown_data_service_from_reimbursement_request",
        ) as cost_breakdown_data_service_from_reimbursement_request, patch(
            "payer_accumulator.accumulation_report_service.AccumulationReportService"
            ".regenerate_and_overwrite_report"
        ) as detail_view, patch(
            "maven.feature_flags.bool_variation", return_value=True
        ):
            detail_view.return_value = cigna_structured_detail_row
            cost_breakdown_data_service_from_reimbursement_request().get_cost_breakdown_data.return_value = (
                accumulation_cost_breakdown_data
            )

            # When
            res = admin_client.post(
                f"/admin/payeraccumulationreports/edit/?id={payer_accumulation_report.id}",
                data=data,
                headers={"Content-Type": "multipart/form-data"},
            )
            # Then
            reimbursement_request = ReimbursementRequest.query.get(
                reimbursement_request.id
            )
            cost_breakdown: CostBreakdown = (
                CostBreakdown.query.filter(
                    CostBreakdown.reimbursement_request_id == reimbursement_request.id
                )
            ).one_or_none()
            new_mapping: AccumulationTreatmentMapping = (
                AccumulationTreatmentMapping.query.filter(
                    AccumulationTreatmentMapping.reimbursement_request_id
                    == reimbursement_request.id
                ).one()
            )
            assert res.status_code == 302
            assert new_mapping.payer_id == test_payer.id
            assert reimbursement_request.amount == reimbursement_request.amount
            assert cost_breakdown
            assert detail_view.call_count == 1
            assert (
                cost_breakdown_data_service_from_reimbursement_request().get_cost_breakdown_data.call_count
                == 1
            )

    def test_reimbursement_request_uses_existing_cb(
        self,
        admin_client,
        payer_accumulation_report,
        test_payer,
        reimbursement_request,
        accumulation_cost_breakdown_data,
        cigna_structured_detail_row,
        form_data,
        accumulation_wallet,
    ):
        # Given
        CostBreakdownFactory.create(
            wallet_id=accumulation_wallet.id,
            reimbursement_request_id=reimbursement_request.id,
        )
        data = form_data(reimbursement_request_id=reimbursement_request.id)
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor"
            ".cost_breakdown_data_service_from_reimbursement_request",
        ) as cost_breakdown_data_service_from_reimbursement_request, patch(
            "payer_accumulator.accumulation_report_service.AccumulationReportService"
            ".regenerate_and_overwrite_report"
        ) as detail_view, patch(
            "maven.feature_flags.bool_variation", return_value=True
        ):
            detail_view.return_value = cigna_structured_detail_row

            # When
            res = admin_client.post(
                f"/admin/payeraccumulationreports/edit/?id={payer_accumulation_report.id}",
                data=data,
                headers={"Content-Type": "multipart/form-data"},
            )
            # Then
            reimbursement_request = ReimbursementRequest.query.get(
                reimbursement_request.id
            )
            new_mapping: AccumulationTreatmentMapping = (
                AccumulationTreatmentMapping.query.filter(
                    AccumulationTreatmentMapping.reimbursement_request_id
                    == reimbursement_request.id
                ).one()
            )
            cost_breakdown: CostBreakdown = (
                CostBreakdown.query.filter(
                    CostBreakdown.reimbursement_request_id == reimbursement_request.id
                )
            ).one()

            assert res.status_code == 302
            assert new_mapping.payer_id == test_payer.id
            assert cost_breakdown.reimbursement_request_id == reimbursement_request.id
            assert reimbursement_request.amount == reimbursement_request.amount
            assert detail_view.call_count == 1
            assert (
                cost_breakdown_data_service_from_reimbursement_request.call_count == 0
            )

    def test_reimbursement_request_cost_breakdown_reimbursement_request_exists(
        self,
        admin_client,
        form_data,
        accumulation_wallet,
        payer_accumulation_report,
        reimbursement_request,
    ):
        with patch("maven.feature_flags.bool_variation", return_value=True):
            # Given
            cb = CostBreakdownFactory.create()
            ReimbursementRequestToCostBreakdownFactory.create(
                claim_type=ClaimType.EMPLOYER,
                treatment_procedure_uuid=uuid.uuid4(),
                reimbursement_request_id=reimbursement_request.id,
                cost_breakdown_id=cb.id,
            )
            data = form_data(reimbursement_request_id=reimbursement_request.id)
            # When
            res = admin_client.post(
                f"/admin/payeraccumulationreports/edit/?id={payer_accumulation_report.id}",
                data=data,
                headers={"Content-Type": "multipart/form-data"},
                follow_redirects=True,
            )
            # Then
            assert res.status_code == 200
            assert b"ReimbursementRequestToCostBreakdown record exists" in res.data

    def test_reimbursement_request_cb_exception(
        self,
        admin_client,
        payer_accumulation_report,
        test_payer,
        reimbursement_request,
        form_data,
        accumulation_wallet,
    ):
        # Given
        data = form_data(reimbursement_request_id=reimbursement_request.id)
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor"
            ".cost_breakdown_data_service_from_reimbursement_request",
        ) as cost_breakdown_data_service_from_reimbursement_request, patch(
            "maven.feature_flags.bool_variation", return_value=True
        ), patch(
            "maven.feature_flags.bool_variation", return_value=True
        ):
            cost_breakdown_data_service_from_reimbursement_request().get_cost_breakdown_data.return_value = (
                {}
            )
            # When
            res = admin_client.post(
                f"/admin/payeraccumulationreports/edit/?id={payer_accumulation_report.id}",
                data=data,
                headers={"Content-Type": "multipart/form-data"},
            )
            # Then
            assert res.status_code == 200
            assert b"Failed to calculate a cost breakdown. Error" in res.data

    def test_reimbursement_request_detail_exception(
        self,
        admin_client,
        payer_accumulation_report,
        test_payer,
        reimbursement_request,
        accumulation_cost_breakdown_data,
        form_data,
    ):
        # Given
        data = form_data(reimbursement_request.id)
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor"
            ".cost_breakdown_data_service_from_reimbursement_request",
        ) as cost_breakdown_data_service_from_reimbursement_request, patch(
            "payer_accumulator.accumulation_report_service.AccumulationReportService"
            ".regenerate_and_overwrite_report"
        ) as detail_view, patch(
            "maven.feature_flags.bool_variation", return_value=True
        ):
            cost_breakdown_data_service_from_reimbursement_request().get_cost_breakdown_data.return_value = (
                accumulation_cost_breakdown_data
            )
            detail_view.side_effect = Exception
            # When
            res = admin_client.post(
                f"/admin/payeraccumulationreports/edit/?id={payer_accumulation_report.id}",
                data=data,
                headers={"Content-Type": "multipart/form-data"},
            )
            # Then
            assert res.status_code == 200
            assert b"Failed to regenerate accumulation" in res.data


class TestTreatmentRowReimbursementRequestUnits:
    def test__update_reimbursement_request(self, reimbursement_request, treatment_row):
        # Given
        cb = CostBreakdownFactory.create()
        original_amount = reimbursement_request.amount
        # when
        updated_request = treatment_row._update_reimbursement_request(
            reimbursement_request, cb
        )
        # Then
        assert updated_request.description.__contains__(
            f"Original Amount: ${convert_cents_to_dollars(original_amount)}"
        )
        assert updated_request.amount == cb.total_employer_responsibility

    def test__validate_reimbursement_request_required_fields_valid(
        self, reimbursement_request, treatment_row
    ):
        # When
        error_message = treatment_row._validate_reimbursement_request_required_fields(
            reimbursement_request
        )
        assert error_message is None

    @pytest.mark.parametrize(
        "rr_data,error_message",
        [
            (
                {
                    "id": 1234,
                    "cost_sharing_category": CostSharingCategory.MEDICAL_CARE.value,
                    "procedure_type": TreatmentProcedureType.MEDICAL.value,
                },
                "You must assign and save a user_id to the reimbursement request's "
                "person_receiving_service.",
            ),
            (
                {
                    "id": 1234,
                    "person_receiving_service_id": 1,
                    "cost_sharing_category": CostSharingCategory.MEDICAL_CARE.value,
                },
                "You must assign and save a procedure_type to the reimbursement request.",
            ),
            (
                {
                    "id": 1234,
                    "person_receiving_service_id": 1,
                    "procedure_type": TreatmentProcedureType.MEDICAL.value,
                },
                "You must assign and save a cost_sharing_category to the reimbursement request.",
            ),
        ],
    )
    def test__validate_reimbursement_request_required_fields_fails(
        self, rr_data, error_message, treatment_row, accumulation_wallet
    ):
        # Given
        category = accumulation_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=accumulation_wallet,
            category=category,
            state=ReimbursementRequestState.APPROVED,
            amount=100,
            **rr_data,
        )
        # when
        actual_error_message = (
            treatment_row._validate_reimbursement_request_required_fields(
                reimbursement_request
            )
        )
        # Then
        assert actual_error_message == error_message

    def test__get_reimbursement_request_cost_breakdown(
        self,
        reimbursement_request,
        accumulation_cost_breakdown_data,
        treatment_row,
    ):
        # Given
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor"
            ".cost_breakdown_data_service_from_reimbursement_request",
        ) as cost_breakdown_data_service_from_reimbursement_request:
            cost_breakdown_data_service_from_reimbursement_request().get_cost_breakdown_data.return_value = (
                accumulation_cost_breakdown_data
            )
            # When
            cost_breakdown = treatment_row._get_reimbursement_request_cost_breakdown(
                reimbursement_request=reimbursement_request,
                user_id=reimbursement_request.person_receiving_service_id,
                cost_sharing_category=CostSharingCategory.MEDICAL_CARE.value,
            )
            # Then
            assert cost_breakdown
            assert (
                cost_breakdown_data_service_from_reimbursement_request.call_count == 2
            )
            assert cost_breakdown.reimbursement_request_id == reimbursement_request.id
