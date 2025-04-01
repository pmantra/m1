from unittest.mock import patch

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)


class TestAggregateProceduresResource:
    def test_get_aggregate_procedures_unauthorized(
        self,
        factories,
        client,
        api_helpers,
    ):
        user = factories.DefaultUserFactory.create()

        res = client.get(
            "/api/v1/direct_payment/clinic/treatment_procedures",
            headers=api_helpers.json_headers(user=user),
        )

        assert res.status_code == 401

    def test_get_aggregate_procedures_unauthorized_standard_fc_user(
        self,
        fc_user,
        client,
        api_helpers,
    ):
        res = client.get(
            "/api/v1/direct_payment/clinic/treatment_procedures",
            headers=api_helpers.json_headers(user=fc_user),
        )

        assert res.status_code == 401

    def test_get_aggregate_procedures_no_treatment_procedures(
        self, client, fc_billing_user, api_helpers
    ):
        res = client.get(
            "/api/v1/direct_payment/clinic/treatment_procedures",
            headers=api_helpers.json_headers(user=fc_billing_user),
        )

        data = api_helpers.load_json(res)

        assert res.status_code == 200
        assert data["total_count"] == 0
        assert data["procedures"] == []

    def test_get_aggregate_procedures(
        self,
        client,
        fc_billing_user,
        enterprise_user,
        treatment_procedures_cycle_based,
        fertility_clinic,
        fertility_clinic_location,
        global_procedure,
        api_helpers,
    ):
        with patch(
            "direct_payment.clinic.resources.aggregate_procedures.get_mapped_global_procedures",
            return_value={
                global_procedure["id"]: global_procedure
                for global_procedure in [global_procedure]
            },
        ):
            res = client.get(
                "/api/v1/direct_payment/clinic/treatment_procedures",
                headers=api_helpers.json_headers(user=fc_billing_user),
            )

            data = api_helpers.load_json(res)

            assert res.status_code == 200
            assert data["total_count"] == len(treatment_procedures_cycle_based)
            for index, resp_procedure in enumerate(data["procedures"]):
                tp = treatment_procedures_cycle_based[index]
                assert resp_procedure["id"] == tp.id
                assert resp_procedure["fertility_clinic_name"] == fertility_clinic.name
                assert (
                    resp_procedure["fertility_clinic_location_name"]
                    == fertility_clinic_location.name
                )
                assert (
                    resp_procedure["fertility_clinic_location_address"]
                    == fertility_clinic_location.address_1
                )
                assert resp_procedure["member_id"] == tp.member_id
                assert resp_procedure["member_first_name"] == enterprise_user.first_name
                assert resp_procedure["member_last_name"] == enterprise_user.last_name
                assert (
                    resp_procedure["member_date_of_birth"]
                    == enterprise_user.health_profile.birthday.isoformat()
                )

    def test_get_aggregate_procedures_member_level_id(
        self,
        client,
        fc_billing_user,
        treatment_procedures_cycle_based,
        global_procedure,
        api_helpers,
    ):
        # Given
        member_benefit_id = "M333333333"

        with patch(
            "direct_payment.clinic.resources.aggregate_procedures.get_mapped_global_procedures"
        ) as mock_get_mapped_gps, patch(
            "wallet.repository.member_benefit.MemberBenefitRepository.get_member_benefit_id"
        ) as mock_get_member_benefit_id:

            mock_get_mapped_gps.return_value = {
                global_procedure["id"]: global_procedure
                for global_procedure in [global_procedure]
            }

            mock_get_member_benefit_id.return_value = member_benefit_id

            # When
            res = client.get(
                "/api/v1/direct_payment/clinic/treatment_procedures",
                headers=api_helpers.json_headers(user=fc_billing_user),
            )

            data = api_helpers.load_json(res)

            assert res.status_code == 200
            assert data["procedures"][0]["benefit_id"] == member_benefit_id

    def test_pagination(
        self,
        client,
        fc_billing_user,
        treatment_procedures_cycle_based,
        global_procedure,
        api_helpers,
    ):
        with patch(
            "direct_payment.clinic.resources.aggregate_procedures.get_mapped_global_procedures"
        ) as mock_get_mapped_gps:
            mock_get_mapped_gps.return_value = {
                global_procedure["id"]: global_procedure
                for global_procedure in [global_procedure]
            }
            limit_param = 2
            res = client.get(
                f"/api/v1/direct_payment/clinic/treatment_procedures?limit={limit_param}&offset=0",
                headers=api_helpers.json_headers(user=fc_billing_user),
            )

            data = api_helpers.load_json(res)

            assert res.status_code == 200
            assert data["total_count"] == len(treatment_procedures_cycle_based)
            assert len(data["procedures"]) == limit_param

    def test_pagination_offset_exceeds_data(
        self,
        client,
        fc_billing_user,
        treatment_procedures_cycle_based,
        global_procedure,
        api_helpers,
    ):
        with patch(
            "direct_payment.clinic.resources.aggregate_procedures.get_mapped_global_procedures"
        ) as mock_get_mapped_gps:
            mock_get_mapped_gps.return_value = {
                global_procedure["id"]: global_procedure
                for global_procedure in [global_procedure]
            }

            res = client.get(
                "/api/v1/direct_payment/clinic/treatment_procedures?limit=10&offset=10",
                headers=api_helpers.json_headers(user=fc_billing_user),
            )

            data = api_helpers.load_json(res)

            assert res.status_code == 200
            assert data["total_count"] == len(treatment_procedures_cycle_based)
            assert len(data["procedures"]) == 0

    def test_sorting(
        self,
        client,
        fc_billing_user,
        treatment_procedures_with_completed_procedures,
        global_procedure,
        api_helpers,
    ):
        with patch(
            "direct_payment.clinic.resources.aggregate_procedures.get_mapped_global_procedures",
            return_value={
                global_procedure["id"]: global_procedure
                for global_procedure in [global_procedure]
            },
        ):
            res = client.get(
                "/api/v1/direct_payment/clinic/treatment_procedures?limit=10&offset=0&sort_by=status&order_direction=asc",
                headers=api_helpers.json_headers(user=fc_billing_user),
            )

            data = api_helpers.load_json(res)

            assert res.status_code == 200
            assert data["total_count"] == len(
                treatment_procedures_with_completed_procedures
            )
            assert (
                data["procedures"][0]["status"]
                == TreatmentProcedureStatus.COMPLETED.value
            )
            assert (
                data["procedures"][-1]["status"]
                == TreatmentProcedureStatus.SCHEDULED.value
            )

    def test_filtering(
        self,
        client,
        fc_billing_user,
        treatment_procedures_with_completed_procedures,
        number_of_completed_treatment_procedures,
        global_procedure,
        api_helpers,
    ):
        with patch(
            "direct_payment.clinic.resources.aggregate_procedures.get_mapped_global_procedures",
            return_value={
                global_procedure["id"]: global_procedure
                for global_procedure in [global_procedure]
            },
        ):
            res = client.get(
                "/api/v1/direct_payment/clinic/treatment_procedures?limit=10&offset=0&sort_by=status&order_direction=asc&status=COMPLETED",
                headers=api_helpers.json_headers(user=fc_billing_user),
            )

            data = api_helpers.load_json(res)

            assert res.status_code == 200
            assert data["total_count"] == number_of_completed_treatment_procedures
            assert all(
                procedure["status"] == TreatmentProcedureStatus.COMPLETED.value
                for procedure in data["procedures"]
            )
