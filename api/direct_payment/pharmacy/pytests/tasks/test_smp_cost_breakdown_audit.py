import datetime
import uuid
from unittest.mock import patch

import factory
import pytest
from maven import feature_flags

from common.global_procedures.procedure import ProcedureService
from cost_breakdown.pytests.factories import CostBreakdownFactory, RTETransactionFactory
from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.billing.pytests.factories import (
    BillFactory,
    BillProcessingRecordFactory,
)
from direct_payment.pharmacy.models.pharmacy_prescription import PrescriptionStatus
from direct_payment.pharmacy.pytests.factories import (
    HealthPlanYearToDateSpendFactory,
    PharmacyPrescriptionFactory,
)
from direct_payment.pharmacy.tasks.smp_cost_breakdown_audit import ErrorInfo
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.factories import DefaultUserFactory
from wallet.models.constants import CostSharingCategory
from wallet.pytests.factories import ReimbursementRequestCategoryFactory
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
)


class TestRxAudit:
    @pytest.mark.parametrize(
        "feature_flag_behavior",
        [NEW_BEHAVIOR, OLD_BEHAVIOR],
    )
    def test_smp_cost_breakdown_audit_individual(
        self,
        feature_flag_behavior,
        multiple_prescriptions,
        individual_member_health_plan,
        rx_audit,
    ):
        # Given
        individual_member_health_plan.subscriber_id = "policy1"
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )
        global_procedure_2 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58q",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS.value,
        )
        ytd_spend = HealthPlanYearToDateSpendFactory.create(
            policy_id="abcdefg",
            first_name="alice",
            last_name="paul",
            year=2024,
            source="MAVEN",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        )
        # When
        with feature_flags.test_data() as ff_test_data:
            ff_test_data.update(
                ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(
                    feature_flag_behavior
                )
            )
            with patch.object(
                ProcedureService,
                "get_procedures_by_ids",
                return_value=[global_procedure_1, global_procedure_2],
            ), patch(
                "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
                return_value=[ytd_spend],
            ):
                (
                    results,
                    users,
                    error_info,
                ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        assert len(users) == 1
        assert len(results) == 3
        assert len(error_info) == 0

    def test_smp_cost_breakdown_audit_tiered_individual(
        self,
        multiple_prescriptions,
        tiered_individual_member_health_plan,
        rx_audit,
    ):
        # Given
        tiered_individual_member_health_plan.subscriber_id = "policy1"
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )
        global_procedure_2 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58q",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS.value,
        )
        ytd_spend = HealthPlanYearToDateSpendFactory.create(
            policy_id="abcdefg",
            first_name="alice",
            last_name="paul",
            year=2024,
            source="MAVEN",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        )
        # When
        with feature_flags.test_data() as ff_test_data:
            ff_test_data.update(
                ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
            )
            with patch.object(
                ProcedureService,
                "get_procedures_by_ids",
                return_value=[global_procedure_1, global_procedure_2],
            ), patch(
                "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
                return_value=[ytd_spend],
            ):
                (
                    results,
                    users,
                    error_info,
                ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        assert len(users) == 1
        assert len(results) == 3
        assert len(error_info) == 0

    def test_smp_cost_breakdown_audit_rx_integrated_future_plan_not_found(
        self,
        wallet,
        individual_member_health_plan,
        pharmacy_prescription_repository,
        rx_audit,
    ):
        # Given
        individual_member_health_plan.subscriber_id = "policy1"
        ytd_spend = HealthPlanYearToDateSpendFactory.create(
            policy_id="abcdefg",
            first_name="alice",
            last_name="paul",
            year=2024,
            source="MAVEN",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        )

        category = ReimbursementRequestCategoryFactory.create(label="fertility")

        cb_1 = CostBreakdownFactory.create(
            wallet_id=wallet.id,
        )
        tp_1 = TreatmentProcedureFactory.create(
            reimbursement_request_category=category,
            cost_breakdown_id=cb_1.id,
            reimbursement_wallet_id=wallet.id,
            global_procedure_id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            member_id=wallet.user_id,
            procedure_type=TreatmentProcedureType.PHARMACY,
            start_date=datetime.datetime(year=2027, month=1, day=5).date(),
        )
        prescription = PharmacyPrescriptionFactory(
            treatment_procedure_id=tp_1.id,
            user_id=wallet.user_id,
            rx_unique_id="test_1",
            status=PrescriptionStatus.SCHEDULED,
        )
        pharmacy_prescription_repository.create(instance=prescription)
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )

        # When
        with feature_flags.test_data() as ff_test_data:
            ff_test_data.update(
                ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
            )
            with patch.object(
                ProcedureService,
                "get_procedures_by_ids",
                return_value=[global_procedure_1],
            ), patch(
                "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
                return_value=individual_member_health_plan,
            ), patch(
                "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
                return_value=[ytd_spend],
            ):
                (
                    results,
                    users,
                    error_info,
                ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

            # Then
            assert len(users) == 1
            assert len(results) == 1
            assert len(error_info) == 1

    def test_smp_cost_breakdown_audit_family_hdhp(
        self, multiple_prescriptions, family_member_health_plan, rx_audit
    ):
        # Given
        family_member_health_plan.subscriber_id = "policy1"
        family_member_health_plan.employer_health_plan.is_hdhp = True
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )
        global_procedure_2 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58q",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS.value,
        )
        ytd_spend = HealthPlanYearToDateSpendFactory.create(
            policy_id="abcdefg",
            first_name="alice",
            last_name="paul",
            year=2024,
            source="MAVEN",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        )
        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=[global_procedure_1, global_procedure_2],
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
            return_value=[ytd_spend],
        ):
            (
                results,
                users,
                error_info,
            ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        assert len(users) == 1
        assert len(results) == 3
        assert len(error_info) == 0

    def test_smp_cost_breakdown_audit_family(
        self, multiple_prescriptions, family_member_health_plan, rx_audit
    ):
        # Given
        family_member_health_plan.subscriber_id = "policy1"
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )
        global_procedure_2 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58q",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS.value,
        )
        ytd_spend = HealthPlanYearToDateSpendFactory.create(
            policy_id="abcdefg",
            first_name="alice",
            last_name="paul",
            year=2024,
            source="MAVEN",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        )
        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=[global_procedure_1, global_procedure_2],
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
            return_value=[ytd_spend],
        ):
            (
                results,
                users,
                error_info,
            ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        assert len(users) == 1
        assert len(results) == 3
        assert len(error_info) == 0

    def test_smp_cost_breakdown_audit_rx_integrated(
        self, rx_integrated_cost_breakdown, individual_member_health_plan, rx_audit
    ):
        # Given
        individual_member_health_plan.subscriber_id = "policy1"
        individual_member_health_plan.employer_health_plan.rx_integrated = True
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )

        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=[global_procedure_1],
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
            return_value=individual_member_health_plan,
        ):
            (
                results,
                users,
                error_info,
            ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        # Then
        assert len(users) == 1
        assert len(results) == 1
        assert len(error_info) == 0

    def test_smp_cost_breakdown_audit_fully_covered(
        self, rx_cost_breakdown_for_treatment_procedure, rx_audit
    ):
        # Given
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )

        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=[global_procedure_1],
        ):
            (
                results,
                users,
                error_info,
            ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        assert len(users) == 1
        assert len(results) == 1
        assert len(error_info) == 1

    def test_smp_cost_breakdown_audit_missing_gp(
        self,
        multiple_prescriptions,
        pharmacy_prescription_service,
        individual_member_health_plan,
        rx_audit,
    ):
        # Given
        today = datetime.datetime.now(tz=datetime.timezone.utc)
        rxs = multiple_prescriptions
        for rx in rxs:
            rx.created_at = today
            pharmacy_prescription_service.update_pharmacy_prescription(instance=rx)

        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=[],
        ):
            (
                results,
                users,
                error_info,
            ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        assert len(users) == 0
        assert len(results) == 0
        assert (
            error_info["general_error"]
            == "Global Procedures request failed to retrieve data."
        )

    def test_smp_cost_breakdown_audit_one_record_fails(
        self,
        multiple_prescriptions,
        pharmacy_prescription_service,
        individual_member_health_plan,
        rx_audit,
    ):
        # Given
        today = datetime.datetime.now(tz=datetime.timezone.utc)
        rxs = multiple_prescriptions
        for rx in rxs:
            rx.created_at = today
            pharmacy_prescription_service.update_pharmacy_prescription(instance=rx)

        individual_member_health_plan.subscriber_id = "policy1"
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )
        global_procedure_2 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58q",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS.value,
        )
        ytd_spend = HealthPlanYearToDateSpendFactory.create(
            policy_id="abcdefg",
            first_name="alice",
            last_name="paul",
            year=2024,
            source="MAVEN",
            deductible_applied_amount=10_000,
            oop_applied_amount=10_000,
        )
        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=[global_procedure_1, global_procedure_2],
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
            side_effect=[[ytd_spend], [ytd_spend], Exception],
        ):
            (
                results,
                users,
                error_info,
            ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        assert len(users) == 1
        assert len(results) == 3
        assert len(error_info) == 1

    def test_no_pharmacy_prescriptions(self, rx_audit):
        # Given
        tomorrow = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
            hours=24
        )

        # Then
        (
            results,
            users,
            error_info,
        ) = rx_audit.calculate_cost_breakdown_audit_for_time_range(start_time=tomorrow)

        # When
        assert users == {}
        assert results == []
        assert (
            error_info["general_error"]
            == "No Pharmacy Prescriptions found for time provided."
        )

    def test_smp_cost_breakdown_audit_missing_cost_share_category(
        self, rx_cost_breakdown_for_treatment_procedure, rx_audit
    ):
        # Given
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=None,
        )

        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=[global_procedure_1],
        ):
            (
                results,
                users,
                error_info,
            ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        assert len(users) == 1
        assert len(results) == 1
        assert len(error_info) == 1

    def test_smp_cost_breakdown_audit_rx_integrated_no_pverify_response(
        self,
        wallet,
        individual_member_health_plan,
        pharmacy_prescription_repository,
        rx_audit,
    ):
        # Given
        individual_member_health_plan.subscriber_id = "policy1"
        individual_member_health_plan.employer_health_plan.rx_integrated = True
        expected_eligibility_info = {
            "individual_deductible": None,
            "individual_deductible_remaining": None,
            "family_deductible": None,
            "family_deductible_remaining": None,
            "individual_oop": None,
            "individual_oop_remaining": None,
            "family_oop": None,
            "family_oop_remaining": None,
            "coinsurance": None,
            "coinsurance_min": None,
            "coinsurance_max": None,
            "copay": None,
            "is_oop_embedded": None,
            "is_deductible_embedded": None,
        }

        category = ReimbursementRequestCategoryFactory.create(label="fertility")
        rte = RTETransactionFactory.create(
            id=1,
            response=expected_eligibility_info,
            request={},
            response_code=200,
            member_health_plan_id=individual_member_health_plan.id,
        )
        cb_1 = CostBreakdownFactory.create(
            wallet_id=wallet.id, rte_transaction_id=rte.id
        )
        tp_1 = TreatmentProcedureFactory.create(
            reimbursement_request_category=category,
            cost_breakdown_id=cb_1.id,
            reimbursement_wallet_id=wallet.id,
            global_procedure_id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            member_id=wallet.user_id,
            procedure_type=TreatmentProcedureType.PHARMACY,
            start_date=datetime.datetime(year=2025, month=1, day=5).date(),
        )
        prescription = PharmacyPrescriptionFactory(
            treatment_procedure_id=tp_1.id,
            user_id=wallet.user_id,
            rx_unique_id="test_1",
            status=PrescriptionStatus.SCHEDULED,
        )
        pharmacy_prescription_repository.create(instance=prescription)
        global_procedure_1 = GlobalProcedureFactory.create(
            id="8af5df5d-ff8c-4158-8427-b2ad6679c58e",
            name="Found Procedure",
            type="pharmacy",
            cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
        )

        # When
        with patch.object(
            ProcedureService,
            "get_procedures_by_ids",
            return_value=[global_procedure_1],
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
            return_value=individual_member_health_plan,
        ):
            (
                results,
                users,
                error_info,
            ) = rx_audit.calculate_cost_breakdown_audit_for_time_range()

        # Then
        assert len(users) == 1
        assert len(results) == 1
        assert len(error_info) == 0

    @pytest.mark.parametrize(
        "ind_ded,ind_remaining,"
        "fam_oop,fam_oop_remaining,"
        "expected_ind_ytd_ded,"
        "expected_fam_oop",
        [
            (25000, 0, 300000, 229309, 25000, 70691),
            (None, 0, 300000, 229309, "Missing individual_deductible ", 70691),
            (
                25000,
                None,
                300000,
                229309,
                "Missing individual_deductible_remaining",
                70691,
            ),
            (25000, 0, 300000, 0, 25000, 300000),
            (25000, 0, 300000, None, 25000, "Missing family_oop_remaining"),
            (25000, 0, None, 0, 25000, "Missing family_oop "),
        ],
    )
    def test__get_rx_integrated_ytd_results(
        self,
        ind_ded,
        ind_remaining,
        fam_oop,
        fam_oop_remaining,
        expected_ind_ytd_ded,
        expected_fam_oop,
        rx_audit,
    ):
        # Given
        expected_eligibility_info = {
            "individual_deductible": ind_ded,
            "individual_deductible_remaining": ind_remaining,
            "family_deductible": 50000,
            "family_deductible_remaining": 25000,
            "individual_oop": 150000,
            "individual_oop_remaining": 79309,
            "family_oop": fam_oop,
            "family_oop_remaining": fam_oop_remaining,
            "coinsurance": 0.0,
            "coinsurance_min": None,
            "coinsurance_max": None,
            "copay": 2000,
        }
        expected_ytd_output = {
            "individual_ytd_deductible": expected_ind_ytd_ded,
            "individual_oop": 70691,
            "family_ytd_deductible": 25000,
            "family_oop": expected_fam_oop,
        }
        # When
        results = rx_audit._get_rx_integrated_ytd_results(expected_eligibility_info)
        # Then
        assert results == expected_ytd_output

    def test_create_error_kwargs(
        self, new_prescription, individual_member_health_plan, rx_audit
    ):
        # Given
        pharmacy_prescription = new_prescription()
        ehp = individual_member_health_plan.employer_health_plan
        category = CostSharingCategory.SPECIALTY_PRESCRIPTIONS
        expected_kwargs = {
            "category": CostSharingCategory.SPECIALTY_PRESCRIPTIONS.value,
            "deductible_embedded": False,
            "drug_name": pharmacy_prescription.rx_name,
            "employer_health_plan_name": ehp.name,
            "fam_ded_limit": 200000,
            "fam_oopm_limit": 300000,
            "ind_ded_limit": 100000,
            "ind_oopm_limit": 200000,
            "is_family_plan": "Individual",
            "is_hdhp": False,
            "member_health_plan_id": individual_member_health_plan.id,
            "oopm_embedded": False,
            "price": pharmacy_prescription.amount_owed,
            "rx_integrated": False,
            "subscriber_id": "abcdefg",
        }
        # when
        kwargs = rx_audit._create_error_kwargs(
            pharmacy_prescription=pharmacy_prescription,
            member_health_plan=individual_member_health_plan,
            category=category,
        )
        assert kwargs == expected_kwargs

    def test_create_error_kwargs_subset(self, new_prescription, rx_audit):
        # Given
        pharmacy_prescription = new_prescription()
        expected_kwargs = {
            "drug_name": pharmacy_prescription.rx_name,
            "price": pharmacy_prescription.amount_owed,
        }
        # when
        kwargs = rx_audit._create_error_kwargs(
            pharmacy_prescription=pharmacy_prescription,
        )
        assert kwargs == expected_kwargs

    def test_set_error_info(
        self,
        treatment_procedure,
        wallet,
        new_prescription,
        individual_member_health_plan,
        rx_audit,
    ):
        # Given
        error_message = "test_error"
        pharmacy_prescription = new_prescription()
        given_kwargs = {
            "deductible_embedded": False,
            "drug_name": pharmacy_prescription.rx_name,
            "employer_health_plan_name": None,
            "is_family_plan": "Individual",
            "is_hdhp": False,
            "member_health_plan_id": individual_member_health_plan.id,
            "oopm_embedded": False,
            "price": pharmacy_prescription.amount_owed,
            "rx_integrated": False,
            "subscriber_id": "abcdefg",
            "fam_ded_limit": 200000,
            "fam_oopm_limit": 300000,
            "ind_ded_limit": 100000,
            "ind_oopm_limit": 200000,
        }
        # when
        errors = rx_audit._set_error_info(
            error_message=error_message,
            errors={},
            treatment_procedure=treatment_procedure,
            benefit_id="12345",
            cost_breakdown_results=[],
            append_result=True,
            wallet=wallet,
            **given_kwargs,
        )
        assert errors[treatment_procedure.id]
        error_info = errors[treatment_procedure.id]
        assert isinstance(error_info, ErrorInfo)
        assert error_info.benefit_id == "12345"
        assert error_info.subscriber_id == "abcdefg"

    @pytest.mark.parametrize(
        "rx_integrated,is_family,expected_len_ids",
        [(True, False, 3), (False, False, 2), (True, True, 6), (False, True, 4)],
    )
    def test_get_procedure_ids(
        self,
        rx_integrated,
        is_family,
        expected_len_ids,
        wallet,
        individual_member_health_plan,
        enterprise_user,
        rx_audit,
    ):
        # means we want all procedure types included
        individual_member_health_plan.employer_health_plan.rx_integrated = rx_integrated
        # primary wallet treatment procedures
        TreatmentProcedureFactory.create_batch(
            size=3,
            reimbursement_wallet_id=wallet.id,
            member_id=wallet.user_id,
            procedure_type=factory.Iterator(
                [
                    TreatmentProcedureType.MEDICAL,
                    TreatmentProcedureType.PHARMACY,
                    TreatmentProcedureType.PHARMACY,
                ]
            ),
        )
        # dependent treatment procedures
        user = DefaultUserFactory.create()
        TreatmentProcedureFactory.create_batch(
            size=3,
            reimbursement_wallet_id=wallet.id,
            member_id=user.id,
            procedure_type=factory.Iterator(
                [
                    TreatmentProcedureType.MEDICAL,
                    TreatmentProcedureType.PHARMACY,
                    TreatmentProcedureType.PHARMACY,
                ]
            ),
        )
        # When
        # if we specify a member only return the procedures for that member not all procedures for the wallet
        member_id = None if is_family else enterprise_user.id
        procedure_ids = rx_audit.get_procedure_ids(
            individual_member_health_plan, wallet=wallet, member_id=member_id
        )
        assert len(procedure_ids) == expected_len_ids

    def test_get_total_ytd_bills(self, billing_service, rx_audit):
        bills = BillFactory.create_batch(
            size=3,
            payor_type=PayorType.MEMBER,
            amount=500,
            procedure_id=factory.Iterator([1, 2, 3]),
            status=factory.Iterator(
                [
                    BillStatus.NEW,
                    BillStatus.PAID,
                    BillStatus.CANCELLED,
                ]
            ),
        )

        for bill in bills:
            saved_bill = billing_service.bill_repo.create(instance=bill)
            trans = uuid.uuid4()
            bpf = BillProcessingRecordFactory.build(
                bill_id=saved_bill.id,
                bill_status=saved_bill.status.value,
                transaction_id=trans,
                processing_record_type="na",
                body="",
            )
            billing_service.bill_processing_record_repo.create(instance=bpf)

        # When
        total_member_bills = rx_audit.get_total_ytd_bills(procedure_ids=[1, 2, 3])

        # Then
        assert total_member_bills == 1000

    @pytest.mark.parametrize("procedure_ids", [([1]), ([])])
    def test_get_ytd_total_member_bills_no_bills(self, procedure_ids, rx_audit):
        # When
        total_member_bills = rx_audit.get_total_ytd_bills(procedure_ids=procedure_ids)

        # Then
        assert total_member_bills == 0
