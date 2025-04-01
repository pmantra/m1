from unittest.mock import patch

from direct_payment.clinic.pytests.factories import FeeScheduleGlobalProceduresFactory


class TestProceduresResource:
    def test_get_clinic_procedures_none_found(
        self,
        fc_user,
        client,
        api_helpers,
        fertility_clinic,
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[],
        ):

            res = client.get(
                f"/api/v1/direct_payment/clinic/fertility_clinics/{fertility_clinic.id}/procedures",
                headers=api_helpers.json_headers(user=fc_user),
            )

            assert res.status_code == 404

    def test_get_clinic_procedures(
        self, fc_user, client, api_helpers, fertility_clinic, global_procedure
    ):
        with patch(
            "common.global_procedures.procedure.ProcedureService.get_procedures_by_ids",
            return_value=[global_procedure],
        ):
            fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory.create(
                cost=34, global_procedure_id=global_procedure["id"]
            )
            fertility_clinic.fee_schedule = fee_schedule_global_procedures.fee_schedule

            res = client.get(
                f"/api/v1/direct_payment/clinic/fertility_clinics/{fertility_clinic.id}/procedures",
                headers=api_helpers.json_headers(user=fc_user),
            )

            procedures = api_helpers.load_json(res)
            assert len(procedures) == 1
            assert procedures[0]["id"] == global_procedure["id"]
            assert procedures[0]["cost"] == 34
