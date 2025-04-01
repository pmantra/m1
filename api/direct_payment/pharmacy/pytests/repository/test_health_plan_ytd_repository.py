import pytest


class TestHealthPlanYTDRepository:
    def test_batch_create(self, health_plan_ytd_spend_repository, esi_ytd_spends):
        row_ids = health_plan_ytd_spend_repository.batch_create(
            instances=esi_ytd_spends, fetch=True
        )
        assert len(row_ids) == 4

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
        health_plan_ytd_spend_repository,
        multiple_ytd_spends,
    ):
        rows = health_plan_ytd_spend_repository.get_all_by_policy(
            policy_id=policy_id,
            year=year,
        )
        assert len(rows) == expected

    @pytest.mark.parametrize(
        argnames="policy_id, year, first_name, last_name, expected",
        argvalues=[
            ("policy1", 2023, "paul", "chris", 3),
            ("policy2", 2023, "james", "justin", 1),
        ],
    )
    @pytest.mark.skip(reason="Flakey on the build server. Blame faker.")
    def test_get_all_by_member(
        self,
        policy_id,
        year,
        first_name,
        last_name,
        expected,
        health_plan_ytd_spend_repository,
        multiple_ytd_spends,
    ):
        rows = health_plan_ytd_spend_repository.get_all_by_member(
            policy_id=policy_id, year=year, first_name=first_name, last_name=last_name
        )
        assert len(rows) == expected
