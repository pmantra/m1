import pytest

from direct_payment.pharmacy.models.health_plan_ytd_spend import Source
from direct_payment.pharmacy.pytests.factories import HealthPlanYearToDateSpendFactory


class TestHealthPlanYTDService:
    @pytest.mark.skip(reason="flaky test to be investigated")
    @pytest.mark.parametrize(
        argnames="policy_id, year, expected",
        argvalues=[
            ("policy1", 2023, 4),
            ("policy1", 2022, 0),
            ("policy2", 2022, 1),
            ("policy2", 2023, 1),
        ],
    )
    def test_get_all_by_policy(
        self,
        policy_id,
        year,
        expected,
        health_plan_ytd_spend_service,
        multiple_ytd_spends,
    ):
        rows = health_plan_ytd_spend_service.get_all_by_policy(
            policy_id=policy_id,
            year=year,
        )
        assert len(rows) == expected

    @pytest.mark.skip(reason="flaky test to be investigated")
    @pytest.mark.parametrize(
        argnames="policy_id, year, first_name, last_name, expected",
        argvalues=[
            ("policy1", 2023, "paul", "chris", 3),
            ("policy2", 2023, "james", "justin", 1),
        ],
    )
    def test_get_all_by_member(
        self,
        policy_id,
        year,
        first_name,
        last_name,
        expected,
        health_plan_ytd_spend_service,
        multiple_ytd_spends,
    ):
        rows = health_plan_ytd_spend_service.get_all_by_member(
            policy_id=policy_id, year=year, first_name=first_name, last_name=last_name
        )
        assert len(rows) == expected

    @pytest.mark.skip(reason="flaky test to be investigated")
    def test_create(self, health_plan_ytd_spend_repository):
        created = health_plan_ytd_spend_repository.create(
            instance=HealthPlanYearToDateSpendFactory.build(
                policy_id="policy1",
                first_name="paul",
                last_name="chris",
                year=2023,
                source="ESI",
                deductible_applied_amount=10_000,
                oop_applied_amount=10_000,
            )
        )
        assert created.policy_id == "policy1"
        assert created.source == Source.ESI
        assert created.deductible_applied_amount == 10_000
        assert created.oop_applied_amount == 10_000
        # clean up
        health_plan_ytd_spend_repository.delete(id=created.id)
