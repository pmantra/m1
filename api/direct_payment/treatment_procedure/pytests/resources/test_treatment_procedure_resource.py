import logging
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from direct_payment.clinic.pytests.factories import FeeScheduleGlobalProceduresFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from wallet.models.constants import AlegeusCoverageTier, PatientInfertilityDiagnosis
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    MemberHealthPlanFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementPlanFactory,
    ReimbursementWalletPlanHDHPFactory,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR

logging.disable(logging.INFO)


class TestTreatmentProcedureResource:
    def test_get_treatment_procedure(
        self, client, api_helpers, fc_user, treatment_procedure
    ):
        res = client.get(
            f"api/v1/direct_payment/treatment_procedure/{treatment_procedure.id}",
            headers=api_helpers.json_headers(user=fc_user),
        )

        assert res.status_code == 200

        data = api_helpers.load_json(res)
        assert data["id"] == treatment_procedure.id
        assert data["uuid"] == treatment_procedure.uuid
        assert data["member_id"] == treatment_procedure.member_id
        assert (
            data["infertility_diagnosis"] == treatment_procedure.infertility_diagnosis
        )
        assert data["fertility_clinic_id"] == treatment_procedure.fertility_clinic_id
        assert (
            data["fertility_clinic_location_id"]
            == treatment_procedure.fertility_clinic_location_id
        )
        assert data["start_date"] == treatment_procedure.start_date.strftime("%Y-%m-%d")
        assert data["global_procedure_id"] == treatment_procedure.global_procedure_id
        assert data["procedure_name"] == treatment_procedure.procedure_name
        assert data["cost"] == treatment_procedure.cost
        assert data["status"] == treatment_procedure.status.value

    def test_get_treatment_procedure_not_exist(
        self,
        client,
        api_helpers,
        fc_user,
    ):
        res = client.get(
            "api/v1/direct_payment/treatment_procedure/1",
            headers=api_helpers.json_headers(user=fc_user),
        )

        assert res.status_code == 404

    @pytest.mark.parametrize(
        argnames=" create_mhp, start_date_offset, plan_setting, exp",
        argvalues=[
            pytest.param(
                False,
                0,
                "ded_acc_enabled",
                400,
                id="1.Success, no change to start date but there no longer is a health plan.",
            ),
            pytest.param(
                False,
                1,
                "ded_acc_enabled",
                400,
                id="2.Failure, Start date changed to a day in the future, no mhp created.",
            ),
            pytest.param(
                False,
                -1,
                "ded_acc_enabled",
                400,
                id="3.Failure, Start date changed to a day in the past, no mhp created.",
            ),
            pytest.param(
                True,
                0,
                "ded_acc_enabled",
                200,
                id="4.Success, no change to start date, mhp present.",
            ),
            pytest.param(
                True,
                1,
                "ded_acc_enabled",
                200,
                id="5.Failure, Start date changed to a day in the future, mhp present.",
            ),
            pytest.param(
                True,
                -1,
                "ded_acc_enabled",
                200,
                id="6.Failure, Start date changed to a day in the past, mhp present.",
            ),
            pytest.param(
                True,
                10,
                "ded_acc_enabled",
                400,
                id="7.Failure, Start date changed to a day in the future, no mhp for new start date.",
            ),
            pytest.param(
                True,
                -10,
                "ded_acc_enabled",
                400,
                id="8.Failure, Start date changed to a day in the past, no mhp for new start date.",
            ),
            pytest.param(
                True,
                -10,
                "hdhp_dtr_for_member_exists",
                400,
                id="9.Failure, Start date changed to a past date, no mhp for new start date. HDHP DTR exists"
                "and no deductible accumulation",
            ),
            pytest.param(
                True,
                -10,
                "hdhp_dtr_for_org_exists",
                400,
                id="10.Failure, Start date changed to a past date, no mhp for new start date. HDHP plan "
                "exists for org, no deductible accumulation on ros. User has not responded to survey.",
            ),
        ],
    )
    def test_put_treatment_procedure(
        self,
        client,
        api_helpers,
        fc_user,
        treatment_procedure,
        fertility_clinic,
        wallet,
        global_procedure,
        ff_test_data,
        hdhp_plan_specify_year,
        create_mhp,
        start_date_offset,
        plan_setting,
        exp,
    ):

        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            plan_setting == "ded_acc_enabled"
        )

        treatment_procedure.start_date = date(2023, 1, 1)
        treatment_procedure.end_date = date(2023, 1, 10)
        treatment_procedure.fertility_clinic_id = fertility_clinic.id
        treatment_procedure.reimbursement_wallet_id = wallet.id

        put_start_date = treatment_procedure.start_date + timedelta(
            days=start_date_offset
        )
        put_end_date = put_start_date + timedelta(days=5)
        put_args = {
            "start_date": put_start_date.strftime("%Y-%m-%d"),
            "end_date": put_end_date.strftime("%Y-%m-%d"),
            "status": "COMPLETED",
        }

        if (
            plan_setting == "hdhp_dtr_for_member_exists"
            or plan_setting == "hdhp_dtr_for_org_exists"
        ):
            rp = hdhp_plan_specify_year(
                put_start_date.year,
                wallet.reimbursement_organization_settings.organization_id,
            )
            if plan_setting == "hdhp_dtr_for_member_exists":
                ReimbursementWalletPlanHDHPFactory(
                    reimbursement_plan_id=rp.id,
                    reimbursement_wallet_id=wallet.id,
                    alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
                )

        if create_mhp:
            _ = MemberHealthPlanFactory.create(
                member_id=treatment_procedure.member_id,
                reimbursement_wallet=wallet,
                plan_start_at=datetime.fromordinal(
                    (treatment_procedure.start_date + timedelta(days=-1)).toordinal()
                ),
                plan_end_at=datetime.fromordinal(
                    (treatment_procedure.start_date + timedelta(days=+1)).toordinal()
                ),
            )
        # test only in NEW_BEHAVIOR mode
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )

        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=global_procedure,
        ), patch(
            "direct_payment.treatment_procedure.utils.procedure_helpers.run_cost_breakdown",
            return_value=True,
        ):
            res = client.put(
                f"api/v1/direct_payment/treatment_procedure/{treatment_procedure.id}",
                headers=api_helpers.json_headers(user=fc_user),
                json=put_args,
            )

            assert res.status_code == exp

            data = api_helpers.load_json(res)
            if exp == 200:
                assert data["start_date"] == put_start_date.strftime("%Y-%m-%d")
                assert data["end_date"] == put_end_date.strftime("%Y-%m-%d")
                assert data["status"] == TreatmentProcedureStatus.COMPLETED.value

    def test_put_treatment_procedure_invalid(
        self,
        client,
        api_helpers,
        fc_user,
        treatment_procedure,
    ):
        put_args = {
            "end_date": "",
            "status": "COMPLETED",
        }

        res = client.put(
            f"api/v1/direct_payment/treatment_procedure/{treatment_procedure.id}",
            headers=api_helpers.json_headers(user=fc_user),
            json=put_args,
        )

        assert res.status_code == 400

    def test_post_treatment_procedure(
        self,
        client,
        api_helpers,
        fc_user,
        wallet_cycle_based: ReimbursementWallet,
        global_procedure,
        fertility_clinic,
        fertility_clinic_location,
        e9y_member_wallet,
    ):
        with patch(
            "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
            return_value=e9y_member_wallet,
        ), patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[global_procedure],
        ), patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=global_procedure,
        ), patch(
            "direct_payment.treatment_procedure.utils.procedure_helpers.run_cost_breakdown",
            return_value=True,
        ) as mock_run_cost_breakdown:
            start_date = date.today() + timedelta(days=8)
            end_date = date.today() + timedelta(days=9)
            wallet_cycle_based.payments_customer_id = (
                "'787af6b3-6592-43e8-8d86-e236caeee155"
            )
            fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory.create(
                cost=34, global_procedure_id=global_procedure["id"]
            )
            fertility_clinic.fee_schedule = fee_schedule_global_procedures.fee_schedule

            post_args = {
                "procedures": [
                    {
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "member_id": wallet_cycle_based.user_id,
                        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE.value,
                        "global_procedure_id": global_procedure["id"],
                        "fertility_clinic_id": fertility_clinic.id,
                        "fertility_clinic_location_id": fertility_clinic_location.id,
                    }
                ]
            }

            res = client.post(
                "api/v1/direct_payment/treatment_procedure",
                headers=api_helpers.json_headers(user=fc_user),
                json=post_args,
            )

            mock_run_cost_breakdown.assert_called_once()
            assert res.status_code == 200

            data = api_helpers.load_json(res)
            tp_data = data["procedures"][0]
            assert tp_data["member_id"] == wallet_cycle_based.user_id
            assert (
                tp_data["infertility_diagnosis"]
                == PatientInfertilityDiagnosis.MEDICALLY_INFERTILE.value
            )
            assert tp_data["fertility_clinic_id"] == fertility_clinic.id
            assert (
                tp_data["fertility_clinic_location_id"] == fertility_clinic_location.id
            )
            assert tp_data["start_date"] == start_date.strftime("%Y-%m-%d")
            assert tp_data["end_date"] == end_date.strftime("%Y-%m-%d")
            assert tp_data["global_procedure_id"] == global_procedure["id"]
            assert tp_data["procedure_name"] == global_procedure["name"]
            assert tp_data["cost_credit"] == global_procedure["credits"]
            assert tp_data["status"] == TreatmentProcedureStatus.SCHEDULED.value

    def test_post_treatment_procedure_no_payment_method_on_file(
        self,
        client,
        api_helpers,
        fc_user,
        wallet_cycle_based,
        global_procedure,
        fertility_clinic,
        fertility_clinic_location,
        ff_test_data,
    ):

        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[global_procedure],
        ), patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=global_procedure,
        ), patch(
            "direct_payment.treatment_procedure.utils.procedure_helpers.run_cost_breakdown",
            return_value=True,
        ), patch(
            "wallet.services.member_lookup.MemberLookupService.is_payment_method_on_file"
        ) as mock_is_payment_method_on_file:
            mock_is_payment_method_on_file.return_value = False

            start_date = date.today() + timedelta(days=8)
            end_date = date.today() + timedelta(days=9)

            fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory.create(
                cost=34, global_procedure_id=global_procedure["id"]
            )
            fertility_clinic.fee_schedule = fee_schedule_global_procedures.fee_schedule

            post_args = {
                "procedures": [
                    {
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "member_id": wallet_cycle_based.user_id,
                        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE.value,
                        "global_procedure_id": global_procedure["id"],
                        "fertility_clinic_id": fertility_clinic.id,
                        "fertility_clinic_location_id": fertility_clinic_location.id,
                    }
                ]
            }

            # When
            res = client.post(
                "api/v1/direct_payment/treatment_procedure",
                headers=api_helpers.json_headers(user=fc_user),
                json=post_args,
            )

        # Then
        assert res.status_code == 400

    def test_post_treatment_procedure_invalid(
        self,
        client,
        api_helpers,
        fc_user,
        wallet_cycle_based,
        global_procedure,
        fertility_clinic,
        fertility_clinic_location,
    ):
        start_date = date.today()
        end_date = date.today() + timedelta(days=1)

        post_args = {
            "procedures": [
                {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "member_id": wallet_cycle_based.user_id,
                    "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE.value,
                    "global_procedure_id": global_procedure["id"],
                    "fertility_clinic_id": fertility_clinic.id,
                    "fertility_clinic_location_id": fertility_clinic_location.id,
                }
            ]
        }

        res = client.post(
            "api/v1/direct_payment/treatment_procedure",
            headers=api_helpers.json_headers(user=fc_user),
            json=post_args,
        )

        assert res.status_code == 400

    def test_post_treatment_procedure_missing_procedures(
        self,
        client,
        api_helpers,
        fc_user,
        wallet_cycle_based,
        global_procedure,
        fertility_clinic,
        fertility_clinic_location,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[],
        ), patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=None,
        ):
            start_date = date.today() + timedelta(days=8)
            end_date = date.today() + timedelta(days=9)

            fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory.create(
                cost=34, global_procedure_id=global_procedure["id"]
            )
            fertility_clinic.fee_schedule = fee_schedule_global_procedures.fee_schedule

            post_args = {
                "procedures": [
                    {
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "member_id": wallet_cycle_based.user_id,
                        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE.value,
                        "global_procedure_id": global_procedure["id"],
                        "fertility_clinic_id": fertility_clinic.id,
                        "fertility_clinic_location_id": fertility_clinic_location.id,
                    }
                ]
            }

            res = client.post(
                "api/v1/direct_payment/treatment_procedure",
                headers=api_helpers.json_headers(user=fc_user),
                json=post_args,
            )
            assert res.status_code == 400

    @pytest.mark.parametrize(
        argnames="mhp_dates_delta, exp",
        argvalues=[
            pytest.param(
                (5, 12),
                200,
                id="1. Member health plan present. Success",
            ),
            pytest.param(
                (15, 22),
                400,
                id="2. No member health plan during tp start date. Failure",
            ),
            pytest.param(
                (15, 22),
                400,
                id="3. No member health plan at all. Failure",
            ),
        ],
    )
    def test_post_treatment_procedure_for_member_health_plan(
        self,
        ff_test_data,
        client,
        api_helpers,
        fc_user,
        wallet_cycle_based,
        global_procedure,
        fertility_clinic,
        fertility_clinic_location,
        e9y_member_wallet,
        mhp_dates_delta,
        exp,
    ):
        with patch(
            "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
            return_value=e9y_member_wallet,
        ), patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[global_procedure],
        ), patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value=global_procedure,
        ), patch(
            "direct_payment.treatment_procedure.utils.procedure_helpers.run_cost_breakdown",
            return_value=True,
        ):
            wallet_cycle_based.reimbursement_organization_settings.deductible_accumulation_enabled = (
                True
            )
            wallet_cycle_based.payments_customer_id = (
                "'787af6b3-6592-43e8-8d86-e236caeee155"
            )
            # Testing the new health repo behaviour
            ff_test_data.update(
                ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
            )
            today_with_time_ = datetime.now(timezone.utc)
            today_ = datetime(
                year=today_with_time_.year,
                month=today_with_time_.month,
                day=today_with_time_.day,
            )
            start_date = today_ + timedelta(days=8)
            end_date = today_ + timedelta(days=9)

            if mhp_dates_delta:
                _ = MemberHealthPlanFactory.create(
                    member_id=wallet_cycle_based.user_id,
                    reimbursement_wallet=wallet_cycle_based,
                    plan_start_at=today_ + timedelta(days=mhp_dates_delta[0]),
                    plan_end_at=today_ + timedelta(days=mhp_dates_delta[1]),
                )

            fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory.create(
                cost=34, global_procedure_id=global_procedure["id"]
            )
            fertility_clinic.fee_schedule = fee_schedule_global_procedures.fee_schedule

            post_args = {
                "procedures": [
                    {
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "member_id": wallet_cycle_based.user_id,
                        "infertility_diagnosis": PatientInfertilityDiagnosis.MEDICALLY_INFERTILE.value,
                        "global_procedure_id": global_procedure["id"],
                        "fertility_clinic_id": fertility_clinic.id,
                        "fertility_clinic_location_id": fertility_clinic_location.id,
                    }
                ]
            }

            res = client.post(
                "api/v1/direct_payment/treatment_procedure",
                headers=api_helpers.json_headers(user=fc_user),
                json=post_args,
            )

            assert res.status_code == exp


class TestTreatmentProcedureMemberResource:
    def test_get_treatment_procedure_member_resource(
        self,
        client,
        api_helpers,
        fc_user,
        global_procedure,
        enterprise_user,
        fertility_clinic,
    ):
        partial_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=enterprise_user.id,
            fertility_clinic=fertility_clinic,
            global_procedure_id=global_procedure["id"],
            status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        )

        parent_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=enterprise_user.id,
            fertility_clinic=fertility_clinic,
            global_procedure_id=global_procedure["id"],
            partial_procedure=partial_treatment_procedure,
            partial_procedure_id=partial_treatment_procedure.id,
            status=TreatmentProcedureStatus.CANCELLED,
        )

        fc_user.clinics = [fertility_clinic]
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[global_procedure],
        ):
            res = client.get(
                f"api/v1/direct_payment/treatment_procedure/member/{enterprise_user.id}",
                headers=api_helpers.json_headers(user=fc_user),
            )

            assert res.status_code == 200

            data = api_helpers.load_json(res)
            assert len(data["procedures"]) == 1

            res_procedure = data["procedures"][0]

            assert res_procedure["id"] == parent_treatment_procedure.id
            assert res_procedure["uuid"] == parent_treatment_procedure.uuid
            assert res_procedure["member_id"] == parent_treatment_procedure.member_id
            assert (
                res_procedure["infertility_diagnosis"]
                == parent_treatment_procedure.infertility_diagnosis
            )
            assert (
                res_procedure["fertility_clinic_id"]
                == parent_treatment_procedure.fertility_clinic_id
            )
            assert (
                res_procedure["fertility_clinic_location_id"]
                == parent_treatment_procedure.fertility_clinic_location_id
            )
            assert res_procedure[
                "start_date"
            ] == parent_treatment_procedure.start_date.strftime("%Y-%m-%d")
            assert (
                res_procedure["global_procedure_id"]
                == parent_treatment_procedure.global_procedure_id
            )
            assert (
                res_procedure["procedure_name"]
                == parent_treatment_procedure.procedure_name
            )
            assert res_procedure["cost"] == parent_treatment_procedure.cost
            assert res_procedure["status"] == parent_treatment_procedure.status.value
            assert (
                res_procedure["partial_procedure"]["id"]
                == partial_treatment_procedure.id
            )

    def test_get_treatment_procedure_member_resource_procedures_not_found(
        self,
        client,
        api_helpers,
        fc_user,
        global_procedure,
        enterprise_user,
        fertility_clinic,
    ):
        partial_treatment_procedure = TreatmentProcedureFactory.create(
            member_id=enterprise_user.id,
            fertility_clinic=fertility_clinic,
            global_procedure_id=global_procedure["id"],
            status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        )

        TreatmentProcedureFactory.create(
            member_id=enterprise_user.id,
            fertility_clinic=fertility_clinic,
            global_procedure_id=global_procedure["id"],
            partial_procedure=partial_treatment_procedure,
            partial_procedure_id=partial_treatment_procedure.id,
            status=TreatmentProcedureStatus.CANCELLED,
        )

        fc_user.clinics = [fertility_clinic]
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[],
        ):
            res = client.get(
                f"api/v1/direct_payment/treatment_procedure/member/{enterprise_user.id}",
                headers=api_helpers.json_headers(user=fc_user),
            )
            assert res.status_code == 404

    def test_get_treatment_procedure_member_resource_no_treatment_procedures(
        self,
        client,
        api_helpers,
        fc_user,
        global_procedure,
        enterprise_user,
        fertility_clinic,
    ):
        fc_user.clinics = [fertility_clinic]
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[],
        ):
            res = client.get(
                f"api/v1/direct_payment/treatment_procedure/member/{enterprise_user.id}",
                headers=api_helpers.json_headers(user=fc_user),
            )
            assert res.status_code == 200
            data = api_helpers.load_json(res)
            assert data["procedures"] == []


@pytest.fixture(scope="function")
def hdhp_plan_specify_year():
    def fn(year: int, organization_id: int):
        plan = ReimbursementPlanFactory.create(
            reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                alegeus_account_type="DTR"
            ),
            alegeus_plan_id="HDHP",
            start_date=date(year=year, month=1, day=1),
            end_date=date(year=year, month=12, day=31),
            is_hdhp=True,
            organization_id=organization_id,
        )
        return plan

    return fn
