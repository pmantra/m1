import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest
from maven import feature_flags

from admin.common_cost_breakdown import CostBreakdownPreviewRow
from admin.views.models.cost_breakdown import CostBreakdownRecalculationView
from cost_breakdown.constants import AmountType, CostBreakdownType, Tier
from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    CostBreakdownData,
    ExtraAppliedAmount,
)
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.clinic.pytests.factories import (
    FeeScheduleFactory,
    FeeScheduleGlobalProceduresFactory,
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import PayerFactory
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.freezegun import freeze_time
from storage.connection import db
from utils.payments import convert_cents_to_dollars
from wallet.models.constants import (
    BenefitTypes,
    CostSharingCategory,
    CostSharingType,
    CoverageType,
    FamilyPlanType,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletState,
    WalletUserMemberStatus,
    WalletUserStatus,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.factories import (
    EmployerHealthPlanCoverageFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
)


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
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COPAY,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            absolute_amount=2000,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def employer_health_plan(employer_health_plan_cost_sharing):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    return EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        cost_sharings=employer_health_plan_cost_sharing,
        coverage=[
            EmployerHealthPlanCoverageFactory(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
                plan_type=FamilyPlanType.FAMILY,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
                coverage_type=CoverageType.RX,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
                plan_type=FamilyPlanType.FAMILY,
                coverage_type=CoverageType.RX,
            ),
        ],
    )


@pytest.fixture(scope="function")
def cost_breakdown_view():
    return CostBreakdownRecalculationView()


@pytest.fixture(scope="function")
def medical_procedure(enterprise_user, wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(
        member_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        procedure_type=TreatmentProcedureType.MEDICAL,
        start_date=datetime.date(year=2025, month=1, day=5),
    )


@pytest.fixture(scope="function")
def member_health_plan(employer_health_plan, wallet, enterprise_user):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet,
        plan_start_at=datetime.datetime(year=2025, month=1, day=1),
        plan_end_at=datetime.datetime(year=2026, month=1, day=1),
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_hdhp(wallet, enterprise_user):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=EmployerHealthPlanFactory.create(is_hdhp=True),
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet,
        plan_start_at=datetime.datetime(year=2025, month=1, day=1),
        plan_end_at=datetime.datetime(year=2026, month=1, day=1),
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_cycle_based(
    employer_health_plan, wallet_cycle_based, enterprise_user
):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet_cycle_based,
    )
    return plan


@pytest.fixture(scope="function")
def fertility_clinic():
    fee_schedule = FeeScheduleFactory.create()
    clinic = FertilityClinicFactory.create(
        id=1, name="test_clinic", fee_schedule=fee_schedule
    )
    FeeScheduleGlobalProceduresFactory.create(
        fee_schedule=fee_schedule, global_procedure_id="gp_id", cost=10000
    )
    return clinic


@pytest.fixture(scope="function")
def fertility_clinic_location(fertility_clinic):
    return FertilityClinicLocationFactory.create(
        name="test_clinic_location",
        fertility_clinic_id=fertility_clinic.id,
        fertility_clinic=fertility_clinic,
    )


@pytest.fixture(scope="function")
def cost_breakdown_data():
    return CostBreakdownData(
        rte_transaction_id=1,
        total_member_responsibility=10000,
        total_employer_responsibility=20000,
        beginning_wallet_balance=100000,
        ending_wallet_balance=90000,
        cost_breakdown_type=CostBreakdownType.FIRST_DOLLAR_COVERAGE,
        amount_type=AmountType.INDIVIDUAL,
        deductible=1000,
        coinsurance=2000,
        oop_applied=3000,
    )


@pytest.fixture(scope="function")
def expected_call_data(enterprise_user):
    def get_data(wallet, procedure_type=TreatmentProcedureType.MEDICAL, tier=None):
        return call(
            member_id=enterprise_user.id,
            wallet=wallet,
            reimbursement_category=wallet.get_direct_payment_category,
            global_procedure_id="gp_id",
            before_this_date=datetime.datetime(
                2025, 1, 1, tzinfo=datetime.timezone.utc
            ),
            asof_date=datetime.datetime(2025, 2, 2),
            service_start_date=datetime.date(2025, 2, 2),
            procedure_type=procedure_type,
            cost=10000,
            tier=tier,
        )

    return get_data


@pytest.fixture
def disqualified_wallet(enterprise_user):
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.DISQUALIFIED, member=enterprise_user
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
    )
    return wallet


@pytest.fixture
def mhp_yoy_feature_flag_on(request):
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(request.param)
        )
        yield ff_test_data


class TestCostBreakdownPreviewerSupports:
    def test_get_clinic_options(self, admin_client):
        fertility_clinic_location_1 = FertilityClinicLocationFactory.create(
            name="test_fc1"
        )
        fertility_clinic_location_2 = FertilityClinicLocationFactory.create(
            name="test_fc2"
        )
        res = admin_client.get("/admin/cost_breakdown_calculator/cliniclocationlist")
        assert [fertility_clinic_location_2.id, "test_fc2"] in res.json
        assert [fertility_clinic_location_1.id, "test_fc1"] in res.json

    def test_get_procedure_list(self, admin_client):
        with patch(
            "common.global_procedures.procedure.ProcedureService.list_all_procedures",
            return_value=[
                GlobalProcedureFactory.create(
                    id="e3e70682-c209-4cac-a29f-6fbed82c07cd", name="IVF", credits=5
                )
            ],
        ):
            res = admin_client.get("/admin/cost_breakdown_calculator/procedurelist")
            assert res.status_code == 200
            assert res.json == [["e3e70682-c209-4cac-a29f-6fbed82c07cd", "IVF"]]

    def test_get_extra_applied_amount_cycle(self, cost_breakdown_view, enterprise_user):
        assert (
            cost_breakdown_view._get_extra_applied_amount(
                member=enterprise_user, benefit_type=BenefitTypes.CYCLE
            )
            == ExtraAppliedAmount()
        )

    def test_get_extra_applied_amount_currency(
        self, cost_breakdown_view, enterprise_user, medical_procedure
    ):
        cb = CostBreakdownFactory.create(
            treatment_procedure_uuid=medical_procedure.uuid,
            total_employer_responsibility=10000,
        )
        medical_procedure.cost_breakdown_id = cb.id

        assert cost_breakdown_view._get_extra_applied_amount(
            member=enterprise_user, benefit_type=BenefitTypes.CURRENCY
        ) == ExtraAppliedAmount(wallet_balance_applied=10000)

    def test_format_cost_breakdown_results(
        self, cost_breakdown_view, member_health_plan
    ):
        cost_breakdown_rows = [
            CostBreakdownPreviewRow(
                member_id="1000",
                total_member_responsibility=1000,
                total_employer_responsibility=2000,
                beginning_wallet_balance=30000,
                ending_wallet_balance=20000,
                deductible=400,
                cost=500,
                overage_amount=600,
                procedure_name="test_medical",
                procedure_type="medical",
                cost_sharing_category="medical_care",
                coinsurance=1000,
                amount_type=AmountType.FAMILY,
                cost_breakdown_type=CostBreakdownType.FIRST_DOLLAR_COVERAGE,
                oop_applied=1000,
                deductible_remaining=0,
                oop_remaining=0,
                family_deductible_remaining=None,
                family_oop_remaining=None,
                is_unlimited=False,
            ),
            CostBreakdownPreviewRow(
                member_id="1000",
                total_member_responsibility=1000,
                total_employer_responsibility=2000,
                beginning_wallet_balance=30000,
                ending_wallet_balance=10000,
                deductible=400,
                cost=500,
                overage_amount=600,
                procedure_name="test_pharmacy",
                procedure_type="pharmacy",
                cost_sharing_category="generic_prescriptions",
                coinsurance=1000,
                amount_type=AmountType.FAMILY,
                cost_breakdown_type=CostBreakdownType.FIRST_DOLLAR_COVERAGE,
                oop_applied=1000,
                deductible_remaining=None,
                oop_remaining=None,
                family_deductible_remaining=0,
                family_oop_remaining=0,
                is_unlimited=False,
            ),
        ]

        res = cost_breakdown_view._format_cost_breakdown_results(
            cost_breakdown_rows, member_health_plan
        )
        expected = {
            "plan": {"name": None, "rxIntegrated": True, "memberId": "1000"},
            "total": {
                "cost": Decimal("10.0"),
                "deductible": Decimal("8.0"),
                "oopApplied": Decimal("20.0"),
                "coinsurance": Decimal("20.0"),
                "copay": Decimal("0"),
                "notCovered": Decimal("12.0"),
                "hraApplied": Decimal("0"),
                "memberResponsibility": Decimal("20.0"),
                "employerResponsibility": Decimal("40.0"),
                "beginningWalletBalance": Decimal("300.0"),
                "endingWalletBalance": Decimal("100.0"),
                "deductibleRemaining": Decimal("0"),
                "oopRemaining": Decimal("0"),
                "familyDeductibleRemaining": Decimal("0"),
                "familyOopRemaining": Decimal("0"),
                "amountType": "FAMILY",
                "costBreakdownType": "FIRST_DOLLAR_COVERAGE",
            },
            "breakdowns": [
                {
                    "memberResponsibility": Decimal("10.0"),
                    "employerResponsibility": Decimal("20.0"),
                    "deductible": Decimal("4.0"),
                    "oopApplied": Decimal("10.0"),
                    "cost": Decimal("5.0"),
                    "procedureName": "test_medical",
                    "procedureType": "medical",
                    "costSharingCategory": "medical_care",
                    "coinsurance": Decimal("10.0"),
                    "copay": Decimal("0"),
                    "overageAmount": Decimal("6.0"),
                    "hraApplied": Decimal("0"),
                },
                {
                    "memberResponsibility": Decimal("10.0"),
                    "employerResponsibility": Decimal("20.0"),
                    "deductible": Decimal("4.0"),
                    "oopApplied": Decimal("10.0"),
                    "cost": Decimal("5.0"),
                    "procedureName": "test_pharmacy",
                    "procedureType": "pharmacy",
                    "costSharingCategory": "generic_prescriptions",
                    "coinsurance": Decimal("10.0"),
                    "copay": Decimal("0"),
                    "overageAmount": Decimal("6.0"),
                    "hraApplied": Decimal("0"),
                },
            ],
        }
        assert res == expected


@pytest.mark.parametrize(
    "mhp_yoy_feature_flag_on", [NEW_BEHAVIOR, OLD_BEHAVIOR], indirect=True
)
class TestCostBreakdownPreviewer:
    def test_submit_multiple_procedures_user_not_found(
        self, admin_client, mhp_yoy_feature_flag_on
    ):
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/multipleprocedures/submit",
            json={"userId": "1"},
            headers={"Content-Type": "application/json"},
        )

        assert res.status_code == 400
        assert res.json["error"] == "User not found"

    def test_submit_multiple_procedures_wallet_user_not_found(
        self,
        enterprise_user,
        admin_client,
        disqualified_wallet,
        mhp_yoy_feature_flag_on,
    ):
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/multipleprocedures/submit",
            json={"userId": str(enterprise_user.id)},
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 400
        assert res.json["error"].startswith(
            "No Qualified wallet associated with this user."
        )

    def test_submit_multiple_procedures_no_direct_payment_category(
        self, enterprise_user, wallet, admin_client, mhp_yoy_feature_flag_on
    ):
        wallet.reimbursement_organization_settings.direct_payment_enabled = False
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/multipleprocedures/submit",
            json={"userId": str(enterprise_user.id)},
            headers={"Content-Type": "application/json"},
        )

        assert res.status_code == 400
        assert res.json["error"].startswith(
            "Could not find wallet direct payment category"
        )

    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_medical_path(
        self,
        enterprise_user,
        wallet,
        member_health_plan,
        fertility_clinic_location,
        admin_client,
        expected_call_data,
        disqualified_wallet,
        mhp_yoy_feature_flag_on,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "clinic_location": {"id": fertility_clinic_location.id},
                            "start_date": "2025-02-02",  # Since this starts after the freeze date,
                            # it appears that we do NOT want this procedure to show up, which contradicts
                            # the assertions below.
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )
            assert res.status_code == 200
            assert (
                cost_breakdown_data_service_from_treatment_procedure.call_args
                == expected_call_data(wallet)
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called_once_with()

    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_hdhp(
        self,
        enterprise_user,
        wallet,
        member_health_plan_hdhp,
        fertility_clinic_location,
        admin_client,
        expected_call_data,
        disqualified_wallet,
        mhp_yoy_feature_flag_on,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "1000",
                    "individualOopLimit": "1000",
                    "familyOop": "",
                    "familyOopLimit": "",
                    "familyDeductible": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "clinic_location": {"id": fertility_clinic_location.id},
                            "start_date": "2025-02-02",  # Since this starts after the freeze date,
                            # it appears that we do NOT want this procedure to show up, which contradicts
                            # the assertions below.
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )
            assert res.status_code == 200
            assert (
                cost_breakdown_data_service_from_treatment_procedure.call_args
                == expected_call_data(wallet)
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called_once_with()

    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_pharmacy_path(
        self,
        enterprise_user,
        wallet,
        member_health_plan,
        fertility_clinic_location,
        admin_client,
        expected_call_data,
        mhp_yoy_feature_flag_on,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "pharmacy",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "cost": 100,
                            "start_date": "2025-02-02",
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

            assert res.status_code == 200
            assert (
                cost_breakdown_data_service_from_treatment_procedure.call_args
                == expected_call_data(
                    wallet, procedure_type=TreatmentProcedureType.PHARMACY
                )
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called_once_with()

    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_sequential_medical_and_pharmacy(
        self,
        enterprise_user,
        wallet,
        member_health_plan,
        fertility_clinic_location,
        admin_client,
        cost_breakdown_data,
        expected_call_data,
        mhp_yoy_feature_flag_on,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.return_value = (
                cost_breakdown_data
            )
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "clinic_location": {"id": fertility_clinic_location.id},
                            "start_date": "2025-02-02",
                        },
                        {
                            "type": "pharmacy",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "cost": 100,
                            "start_date": "2025-02-02",
                        },
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

            assert res.status_code == 200
            assert (
                cost_breakdown_data_service_from_treatment_procedure.call_args
                == expected_call_data(
                    wallet, procedure_type=TreatmentProcedureType.PHARMACY
                )
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called()

    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_rte_override(
        self,
        enterprise_user,
        wallet,
        member_health_plan,
        fertility_clinic_location,
        admin_client,
        cost_breakdown_data,
        expected_call_data,
        mhp_yoy_feature_flag_on,
    ):
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            True
        )
        cost_breakdown_data_service = MagicMock(
            get_cost_breakdown_data=MagicMock(
                return_value=CostBreakdownFactory.create(
                    cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION
                )
            ),
            override_rte_result=None,
        )
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
            return_value=cost_breakdown_data_service,
        ) as cost_breakdown_data_service_from_treatment_procedure:
            member_health_plan.employer_health_plan.created_at = (
                datetime.datetime.strptime("23/10/2024 00:00", "%d/%m/%Y %H:%M")
            )
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "100",
                    "individualOop": "100",
                    "familyDeductible": "100",
                    "familyOop": "100",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "clinic_location": {"id": fertility_clinic_location.id},
                            "start_date": "2025-02-02",
                        },
                        {
                            "type": "pharmacy",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "cost": 100,
                            "start_date": "2025-02-02",
                        },
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

            assert "error" not in res.json
            assert res.status_code == 200
            assert cost_breakdown_data_service_from_treatment_procedure.call_args_list[
                0
            ] == expected_call_data(wallet)
            assert cost_breakdown_data_service_from_treatment_procedure.call_args_list[
                1
            ] == expected_call_data(
                wallet, procedure_type=TreatmentProcedureType.PHARMACY
            )
            cost_breakdown_data_service.get_cost_breakdown_data.assert_called()
            assert cost_breakdown_data_service.override_rte_result == EligibilityInfo(
                individual_deductible=200000,
                individual_deductible_remaining=190000,
                family_deductible=None,
                family_deductible_remaining=None,
                individual_oop=400000,
                individual_oop_remaining=390000,
                family_oop=None,
                family_oop_remaining=None,
                coinsurance=None,
                coinsurance_min=None,
                coinsurance_max=None,
                copay=2000,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            )

    @pytest.mark.parametrize(
        argnames="credits,expected_wallet_balance",
        argvalues=[(3, 10000), (5, 10000), (24, 5000.0)],
    )
    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_medical_path_cycle_based(
        self,
        credits,
        expected_wallet_balance,
        enterprise_user,
        wallet_cycle_based,
        member_health_plan_cycle_based,
        fertility_clinic_location,
        admin_client,
        mhp_yoy_feature_flag_on,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=credits),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "clinic_location": {"id": fertility_clinic_location.id},
                            "start_date": "2025-02-02",
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

            assert res.status_code == 200
            assert cost_breakdown_data_service_from_treatment_procedure.call_args == call(
                member_id=enterprise_user.id,
                wallet=wallet_cycle_based,
                reimbursement_category=wallet_cycle_based.get_direct_payment_category,
                global_procedure_id="gp_id",
                before_this_date=datetime.datetime(
                    2025, 1, 1, tzinfo=datetime.timezone.utc
                ),
                asof_date=datetime.datetime(2025, 2, 2),
                service_start_date=datetime.date(2025, 2, 2),
                procedure_type=TreatmentProcedureType.MEDICAL,
                cost=10000,
                tier=None,
                wallet_balance_override=expected_wallet_balance,
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called_once_with()

    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_pharmacy_path_cycle_based(
        self,
        enterprise_user,
        wallet_cycle_based,
        member_health_plan_cycle_based,
        admin_client,
        expected_call_data,
        mhp_yoy_feature_flag_on,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "pharmacy",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "cost": 100,
                            "start_date": "2025-02-02",
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

            assert res.status_code == 200
            assert cost_breakdown_data_service_from_treatment_procedure.call_args == call(
                member_id=enterprise_user.id,
                wallet=wallet_cycle_based,
                reimbursement_category=wallet_cycle_based.get_direct_payment_category,
                global_procedure_id="gp_id",
                before_this_date=datetime.datetime(
                    2025, 1, 1, tzinfo=datetime.timezone.utc
                ),
                asof_date=datetime.datetime(2025, 2, 2),
                service_start_date=datetime.date(2025, 2, 2),
                procedure_type=TreatmentProcedureType.PHARMACY,
                cost=10000,
                tier=None,
                wallet_balance_override=10000,
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called_once_with()

    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_sequential_medical_and_pharmacy_cycle_based(
        self,
        enterprise_user,
        wallet_cycle_based,
        member_health_plan_cycle_based,
        fertility_clinic_location,
        admin_client,
        cost_breakdown_data,
        expected_call_data,
        mhp_yoy_feature_flag_on,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.return_value = (
                cost_breakdown_data
            )
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "clinic_location": {"id": fertility_clinic_location.id},
                            "start_date": "2025-02-02",
                        },
                        {
                            "type": "pharmacy",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "cost": 100,
                            "start_date": "2025-02-02",
                        },
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

            assert res.status_code == 200
            assert cost_breakdown_data_service_from_treatment_procedure.call_args == call(
                member_id=enterprise_user.id,
                wallet=wallet_cycle_based,
                reimbursement_category=wallet_cycle_based.get_direct_payment_category,
                global_procedure_id="gp_id",
                before_this_date=datetime.datetime(
                    2025, 1, 1, tzinfo=datetime.timezone.utc
                ),
                asof_date=datetime.datetime(2025, 2, 2),
                service_start_date=datetime.date(2025, 2, 2),
                procedure_type=TreatmentProcedureType.PHARMACY,
                cost=10000,
                tier=None,
                wallet_balance_override=10000,
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called()

    @freeze_time("2025-1-1", tick=False)
    def test_submit_multiple_procedures_sequential_medical_and_pharmacy_tiered(
        self,
        enterprise_user,
        wallet,
        employer_health_plan_cost_sharing,
        fertility_clinic_location,
        admin_client,
        cost_breakdown_data,
        expected_call_data,
        mhp_yoy_feature_flag_on,
    ):
        employer_health_plan = EmployerHealthPlanFactory.create(
            cost_sharings=employer_health_plan_cost_sharing,
            coverage=[
                EmployerHealthPlanCoverageFactory.create(
                    individual_deductible=200_000,
                    individual_oop=400_000,
                    family_deductible=400_000,
                    family_oop=600_000,
                    tier=Tier.PREMIUM,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    individual_deductible=50000,
                    individual_oop=100_000,
                    family_deductible=100_000,
                    family_oop=200_000,
                    coverage_type=CoverageType.RX,
                    tier=Tier.PREMIUM,
                ),
            ],
        )
        wallet.user_id = enterprise_user.id
        MemberHealthPlanFactory.create(
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=employer_health_plan.id,
            is_subscriber=True,
            member_id=enterprise_user.id,
            reimbursement_wallet=wallet,
            plan_start_at=datetime.datetime(year=2025, month=1, day=1),
            plan_end_at=datetime.datetime(year=2026, month=1, day=1),
        )
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure:
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.return_value = (
                cost_breakdown_data
            )
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "clinic_location": {"id": fertility_clinic_location.id},
                            "start_date": "2025-02-02",
                        },
                        {
                            "type": "pharmacy",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "cost": 100,
                            "start_date": "2025-02-02",
                        },
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

            assert res.status_code == 200
            assert (
                cost_breakdown_data_service_from_treatment_procedure.call_args
                == expected_call_data(
                    wallet,
                    procedure_type=TreatmentProcedureType.PHARMACY,
                    tier=Tier.PREMIUM,
                )
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called()

    @freeze_time("2025-1-1", tick=False)
    def test_submit_procedure_pharmacy_tiered_override(
        self,
        enterprise_user,
        wallet,
        employer_health_plan_cost_sharing,
        fertility_clinic_location,
        admin_client,
        cost_breakdown_data,
        expected_call_data,
        mhp_yoy_feature_flag_on,
    ):
        employer_health_plan = EmployerHealthPlanFactory.create(
            cost_sharings=employer_health_plan_cost_sharing,
            coverage=[
                EmployerHealthPlanCoverageFactory.create(
                    individual_deductible=50000,
                    individual_oop=100_000,
                    family_deductible=100_000,
                    family_oop=200_000,
                    coverage_type=CoverageType.RX,
                    tier=Tier.SECONDARY,
                ),
            ],
        )
        wallet.user_id = enterprise_user.id
        MemberHealthPlanFactory.create(
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=employer_health_plan.id,
            is_subscriber=True,
            member_id=enterprise_user.id,
            reimbursement_wallet=wallet,
            plan_start_at=datetime.datetime(year=2025, month=1, day=1),
            plan_end_at=datetime.datetime(year=2026, month=1, day=1),
        )
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.return_value = (
                cost_breakdown_data
            )
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "pharmacy",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "cost": 100,
                            "start_date": "2025-02-02",
                            "tier": "2",
                        },
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

            assert res.status_code == 200
            assert (
                cost_breakdown_data_service_from_treatment_procedure.call_args
                == expected_call_data(
                    wallet,
                    procedure_type=TreatmentProcedureType.PHARMACY,
                    tier=Tier.SECONDARY,
                )
            )

    @freeze_time("2025-01-01", tick=False)
    def test_submit_multiple_procedures_medical_path_previous_scheduled_tps(
        self,
        enterprise_user,
        wallet,
        member_health_plan,
        fertility_clinic_location,
        medical_procedure,
        admin_client,
        expected_call_data,
        mhp_yoy_feature_flag_on,
    ):
        cb = CostBreakdownFactory.create(
            oop_applied=100000, total_employer_responsibility=100000
        )
        medical_procedure.cost_breakdown_id = cb.id
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=GlobalProcedureFactory.create(name="IVF", credits=5),
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure, patch(
            "admin.views.models.cost_breakdown.CostBreakdownRecalculationView._format_cost_breakdown_results",
            return_value={},
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/multipleprocedures/submit",
                json={
                    "userId": str(enterprise_user.id),
                    "individualDeductible": "",
                    "individualOop": "",
                    "familyDeductible": "",
                    "familyOop": "",
                    "hraRemaining": "",
                    "procedures": [
                        {
                            "type": "medical",
                            "procedure": {"id": "gp_id", "name": "IVF"},
                            "clinic_location": {"id": fertility_clinic_location.id},
                            "start_date": "2025-02-02",
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )
            assert res.status_code == 200
            assert (
                cost_breakdown_data_service_from_treatment_procedure.call_args
                == expected_call_data(wallet)
            )
            cost_breakdown_data_service_from_treatment_procedure().get_cost_breakdown_data.assert_called_once_with()


class TestCostBreakdownPreviewerLinksReimbursement:
    @pytest.mark.parametrize(
        "total_member_responsibility,total_employer_responsibility,"
        "expected_amount,expected_state,mapping_count,flash_count, alegeus_count",
        [
            (12500, 32500, 32500, "PENDING", 0, 2, 1),
            (100_00, 0, 100_00, "DENIED", 1, 2, 0),
        ],
    )
    def test_link_reimbursement_successful(
        self,
        total_member_responsibility,
        total_employer_responsibility,
        expected_amount,
        expected_state,
        mapping_count,
        flash_count,
        alegeus_count,
        enterprise_user,
        wallet,
        admin_client,
    ):
        org_setting = wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = True
        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            amount=expected_amount,
            state=ReimbursementRequestState.NEW,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            description="",
            service_start_date=datetime.datetime.now(datetime.timezone.utc),
        )
        MemberHealthPlanFactory.create(
            reimbursement_wallet=wallet,
            reimbursement_wallet_id=wallet.id,
            member_id=enterprise_user.id,
            employer_health_plan=EmployerHealthPlanFactory.create(
                name="Test Plan",
            ),
        )
        with patch(
            "payer_accumulator.accumulation_mapping_service.AccumulationMappingService.create_valid_reimbursement_request_mapping"
        ) as mapping_call, patch(
            "admin.common_cost_breakdown.handle_reimbursement_request_state_change"
        ) as alegeus_call, patch(
            "admin.common_cost_breakdown.flash"
        ) as flash:
            mapping_call.return_value = None
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/linkreimbursement",
                json={
                    "memberId": f"{enterprise_user.id}",
                    "reimbursementRequestId": f"{reimbursement.id}",
                    "totalCost": convert_cents_to_dollars(expected_amount),
                    "memberResponsibility": convert_cents_to_dollars(
                        total_member_responsibility
                    ),
                    "employerResponsibility": convert_cents_to_dollars(
                        total_employer_responsibility
                    ),
                    "deductible": 500,
                    "oopApplied": 750,
                    "deductibleRemaining": 1500,
                    "oopRemaining": 2250,
                    "familyDeductibleRemaining": 0,
                    "familyOopRemaining": 4500,
                    "copay": 40,
                    "coinsurance": 285,
                    "beginningWalletBalance": 2000,
                    "endingWalletBalance": 1675,
                    "hraApplied": 325,
                    "overageAmount": 0,
                    "amountType": "FAMILY",
                    "costBreakdownType": "DEDUCTIBLE_ACCUMULATION",
                    "description": "Test Description",
                },
                headers={"Content-Type": "application/json"},
            )
            assert res.status_code == 200
            cb: CostBreakdown = (
                db.session.query(CostBreakdown)
                .filter(CostBreakdown.reimbursement_request_id == reimbursement.id)
                .one()
            )
            rr: ReimbursementRequest = (
                db.session.query(ReimbursementRequest)
                .filter(ReimbursementRequest.id == reimbursement.id)
                .one()
            )
            assert cb.member_id == enterprise_user.id
            assert cb.total_member_responsibility == total_member_responsibility
            assert cb.total_employer_responsibility == total_employer_responsibility
            assert cb.deductible == 50000
            assert cb.oop_applied == 75000
            assert cb.oop_remaining == 225000
            assert cb.deductible_remaining == 150000
            assert cb.family_oop_remaining == 450000
            assert cb.family_deductible_remaining == 0
            assert cb.copay == 4000
            assert cb.coinsurance == 28500
            assert cb.beginning_wallet_balance == 200000
            assert cb.ending_wallet_balance == 167500
            assert cb.hra_applied == 32500
            assert cb.overage_amount == 0
            assert cb.amount_type == AmountType.FAMILY
            assert cb.cost_breakdown_type == CostBreakdownType.DEDUCTIBLE_ACCUMULATION
            assert mapping_call.call_count == mapping_count
            assert rr.amount == expected_amount
            assert rr.state == ReimbursementRequestState(expected_state)
            assert rr.description.__contains__("Test Plan")
            assert rr.description.__contains__("Test Description")
            assert (
                rr.person_receiving_service_member_status
                == WalletUserMemberStatus.MEMBER
            )
            assert flash.call_count == flash_count
            assert alegeus_call.call_count == alegeus_count
            main_message = flash.call_args_list[0].args[0]
            assert f"Cost Breakdown <{cb.id}> saved!" in main_message

    def test_link_reimbursement_wrong_state(
        self,
        admin_client,
        wallet,
        enterprise_user,
    ):
        org_setting = wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = True
        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement = ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            amount=100,
            state=ReimbursementRequestState.PENDING,
        )
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/linkreimbursement",
            json={
                "memberId": f"{enterprise_user.id}",
                "reimbursementRequestId": f"{reimbursement.id}",
                "totalCost": 1,
                "memberResponsibility": 1,
                "employerResponsibility": 1,
                "deductible": 500,
                "oopApplied": 750,
                "deductibleRemaining": 1500,
                "oopRemaining": 2250,
                "familyDeductibleRemaining": 0,
                "familyOopRemaining": 4500,
                "copay": 40,
                "coinsurance": 285,
                "beginningWalletBalance": 2000,
                "endingWalletBalance": 1675,
                "hraApplied": 325,
                "overageAmount": 0,
                "amountType": "FAMILY",
                "costBreakdownType": "DEDUCTIBLE_ACCUMULATION",
                "description": "Test Description",
            },
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 400

    @pytest.mark.parametrize(
        "is_deductible_accumulation,total_member_responsibility,total_employer_responsibility,"
        "expected_amount,expected_state,claims_calls,flash_count,accumulations",
        [
            # member responsibility == amount
            (False, 100, 0, 100, "DENIED", 1, 2, 0),
            (True, 100, 0, 100, "DENIED", 0, 2, 1),
            # divided responsibility
            (False, 25, 75, 75, "APPROVED", 2, 2, 0),
            (True, 25, 75, 75, "APPROVED", 1, 2, 1),
            # employer responsibility == amount
            (False, 0, 100, 100, "APPROVED", 1, 2, 0),
            (True, 0, 100, 100, "APPROVED", 1, 2, 0),
        ],
        ids=[
            "memb_resp_not_da",
            "memb_resp_da",
            "divided_resp_not_da",
            "divided_resp_da",
            "employer_resp_not_da",
            "employer_resp_da",
        ],
    )
    def test_link_reimbursement_saves_auto_processed_rx(
        self,
        admin_client,
        wallet,
        enterprise_user,
        is_deductible_accumulation,
        total_member_responsibility,
        total_employer_responsibility,
        expected_amount,
        expected_state,
        claims_calls,
        flash_count,
        accumulations,
    ):
        MemberHealthPlanFactory.create(
            reimbursement_wallet=wallet,
            reimbursement_wallet_id=wallet.id,
            member_id=enterprise_user.id,
            employer_health_plan=EmployerHealthPlanFactory.create(
                name="Test Plan",
                is_hdhp=True,
            ),
        )
        PayerFactory.create(id=1, payer_name=PayerName.UHC, payer_code="uhc_code")
        org_setting = wallet.reimbursement_organization_settings
        org_setting.deductible_accumulation_enabled = is_deductible_accumulation

        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement_request = ReimbursementRequestFactory.create(
            reimbursement_wallet_id=wallet.id,
            reimbursement_request_category_id=category.id,
            reimbursement_type=ReimbursementRequestType.MANUAL,
            procedure_type=TreatmentProcedureType.PHARMACY.value,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            person_receiving_service_id=wallet.user_id,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
            cost_credit=0,
            amount=100,
            auto_processed=ReimbursementRequestAutoProcessing.RX,
            person_receiving_service_member_status=WalletUserMemberStatus.MEMBER,
        )
        with patch(
            "direct_payment.pharmacy.automated_reimbursement_request_service"
            ".create_auto_processed_claim_in_alegeus",
            return_value=True,
        ) as submit_claims_to_alegeus, patch(
            "admin.common_cost_breakdown.flash"
        ) as flash, patch(
            "wallet.services.reimbursement_request_state_change"
            ".use_alegeus_for_reimbursements",
            return_value=True,
        ), patch(
            "braze.client.BrazeClient._make_request"
        ) as mock_send_event:
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/linkreimbursement",
                json={
                    "memberId": f"{enterprise_user.id}",
                    "reimbursementRequestId": f"{reimbursement_request.id}",
                    "totalCost": 100,
                    "memberResponsibility": convert_cents_to_dollars(
                        total_member_responsibility
                    ),
                    "employerResponsibility": convert_cents_to_dollars(
                        total_employer_responsibility
                    ),
                    "deductible": convert_cents_to_dollars(total_member_responsibility),
                    "oopApplied": 0,
                    "deductibleRemaining": 1500,
                    "oopRemaining": 2250,
                    "familyDeductibleRemaining": 0,
                    "familyOopRemaining": 4500,
                    "copay": 40,
                    "coinsurance": 285,
                    "beginningWalletBalance": 2000,
                    "endingWalletBalance": 1675,
                    "hraApplied": 325,
                    "overageAmount": 0,
                    "amountType": "FAMILY",
                    "costBreakdownType": "DEDUCTIBLE_ACCUMULATION",
                    "description": "Test Description",
                },
                headers={"Content-Type": "application/json"},
            )
        assert res.status_code == 200
        rr = ReimbursementRequest.query.filter(
            ReimbursementRequest.id == reimbursement_request.id
        ).one()
        assert rr.amount == expected_amount
        assert rr.state == ReimbursementRequestState(expected_state)

        cost_breakdown = CostBreakdown.query.filter(
            CostBreakdown.reimbursement_request_id == reimbursement_request.id
        ).one()

        assert flash.call_count == flash_count
        main_message = flash.call_args_list[0].args[0]
        assert f"Cost Breakdown <{cost_breakdown.id}> saved!" in main_message
        assert submit_claims_to_alegeus.call_count == claims_calls

        accumulation_mapping = AccumulationTreatmentMapping.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        assert len(accumulation_mapping) == accumulations
        assert mock_send_event.call_count == 1

    def test_check_existing_breakdown(self, admin_client, wallet, enterprise_user):
        org_setting = wallet.reimbursement_organization_settings
        category = org_setting.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
        reimbursement = ReimbursementRequestFactory.create(
            wallet=wallet,
            amount=100,
            state=ReimbursementRequestState.NEW,
            category=category,
        )

        # Test when no breakdown exists
        res = admin_client.get(
            f"/admin/cost_breakdown_calculator/check_existing/{reimbursement.id}"
        )
        assert res.status_code == 200
        assert res.json["exists"] == False

        # Create breakdown and test again
        CostBreakdownFactory.create(
            reimbursement_request_id=reimbursement.id,
            wallet_id=wallet.id,
            member_id=enterprise_user.id,
            total_member_responsibility=5000,
            total_employer_responsibility=5000,
        )

        res = admin_client.get(
            f"/admin/cost_breakdown_calculator/check_existing/{reimbursement.id}"
        )
        assert res.status_code == 200
        assert res.json["exists"] == True
