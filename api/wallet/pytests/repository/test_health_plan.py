import datetime

import pytest
from maven import feature_flags
from sqlalchemy.orm.exc import MultipleResultsFound

from wallet.models.constants import (
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.pytests.factories import EmployerHealthPlanFactory, MemberHealthPlanFactory
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    LOGGING_BEHAVIOR,
    NEW_BEHAVIOR,
    HealthPlanRepository,
)


@pytest.fixture
def health_plan_repo(db):
    return HealthPlanRepository(db.session)


@pytest.fixture()
def enable_new_behavior():
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )
        yield ff_test_data


@pytest.fixture()
def enable_logging_behavior():
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(LOGGING_BEHAVIOR)
        )
        yield ff_test_data


class TestHealthPlanRepository:
    def test_get_member_plan(self, health_plan_repo, db):
        new_mhp = MemberHealthPlanFactory.create()
        db.session.expire(
            new_mhp
        )  # prevent the factory from putting a different datetime format in the session

        expected_mhp = MemberHealthPlan.query.get(new_mhp.id)
        mhp = health_plan_repo.get_member_plan(id=new_mhp.id)

        assert mhp == expected_mhp

    def test_get_employer_plan(self, health_plan_repo, db):
        new_ehp = EmployerHealthPlanFactory.create()
        new_mhp = MemberHealthPlanFactory.create(
            employer_health_plan=new_ehp,
            reimbursement_wallet__reimbursement_organization_settings=new_ehp.reimbursement_organization_settings,
        )
        db.session.expire(new_ehp)
        db.session.expire(
            new_mhp
        )  # prevent the factory from putting a different datetime format in the session

        expected_ehp = EmployerHealthPlan.query.get(new_ehp.id)
        ehp = health_plan_repo.get_employer_plan(id=new_ehp.id)

        assert ehp == expected_ehp

    def test_get_employer_plan_from_member_plan(self, health_plan_repo, db):
        new_ehp = EmployerHealthPlanFactory.create()
        new_mhp = MemberHealthPlanFactory.create(
            employer_health_plan=new_ehp,
            reimbursement_wallet__reimbursement_organization_settings=new_ehp.reimbursement_organization_settings,
        )
        db.session.expire(new_ehp)
        db.session.expire(
            new_mhp
        )  # prevent the factory from putting a different datetime format in the session

        expected_ehp = EmployerHealthPlan.query.get(new_ehp.id)
        ehp = health_plan_repo.get_employer_plan_by_member_health_plan_id(id=new_mhp.id)

        assert ehp == expected_ehp

    @pytest.mark.parametrize(
        "effective_date_adjustment, expected_result",
        [
            pytest.param({"days": -10}, False, id="before start date"),
            pytest.param({"days": 0}, True, id="exactly equal to start date"),
            pytest.param({"days": 10}, True, id="during the plan"),
            pytest.param({"days": 365}, True, id="exactly equal to the end date"),
            pytest.param({"days": 365 * 2}, False, id="after the plan"),
        ],
    )
    def test_get_member_plan_by_wallet_and_member_id(
        self,
        health_plan_repo,
        effective_date_adjustment: dict,
        expected_result,
        enable_new_behavior,
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        mhp = MemberHealthPlanFactory.create(
            plan_start_at=start_date,
            plan_end_at=start_date + datetime.timedelta(days=365),
        )
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        res = health_plan_repo.get_member_plan_by_wallet_and_member_id(
            member_id=mhp.member_id,
            wallet_id=mhp.reimbursement_wallet_id,
            effective_date=effective_date,
        )
        assert res == (mhp if expected_result is True else None)

    @pytest.mark.parametrize(
        "effective_date_adjustment",
        [
            pytest.param({"days": -10}, id="before start date"),
            pytest.param({"days": 0}, id="exactly equal to start date"),
            pytest.param({"days": 10}, id="during the plan"),
            pytest.param({"days": 365}, id="exactly equal to the end date"),
            pytest.param({"days": 365 * 2}, id="after the plan"),
        ],
    )
    def test_logging_behavior_member_plan(
        self, health_plan_repo, effective_date_adjustment, enable_logging_behavior
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        mhp = MemberHealthPlanFactory.create(
            plan_start_at=start_date,
            plan_end_at=start_date + datetime.timedelta(days=365),
        )
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        res = health_plan_repo.get_member_plan_by_wallet_and_member_id(
            member_id=mhp.member_id,
            wallet_id=mhp.reimbursement_wallet_id,
            effective_date=effective_date,
        )

        # when logging, all results should be the same.
        assert res == mhp

    @pytest.mark.parametrize(
        "effective_date_adjustment, expected_result",
        [
            pytest.param({"days": -10}, False, id="before start date"),
            pytest.param({"days": 0}, True, id="exactly equal to start date"),
            pytest.param({"days": 10}, True, id="during the plan"),
        ],
    )
    def test_get_member_plan_by_wallet_and_member_id_open_ended_plan(
        self,
        health_plan_repo,
        effective_date_adjustment: dict,
        expected_result,
        enable_new_behavior,
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        mhp = MemberHealthPlanFactory.create(plan_start_at=start_date, plan_end_at=None)
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        res = health_plan_repo.get_member_plan_by_wallet_and_member_id(
            member_id=mhp.member_id,
            wallet_id=mhp.reimbursement_wallet_id,
            effective_date=effective_date,
        )
        assert res == (mhp if expected_result is True else None)

    @pytest.mark.parametrize(
        "effective_date_adjustment, expected_result",
        [
            pytest.param({"days": -100}, 0, id="before first plan"),
            pytest.param({"days": 10}, 1, id="during first plan"),
            pytest.param({"days": 365 + 100}, 0, id="between plans"),
            pytest.param({"days": 365 * 4}, 2, id="during second plan"),
        ],
    )
    def test_get_member_plan_by_wallet_and_member_id_many_plans(
        self,
        health_plan_repo,
        effective_date_adjustment: dict,
        expected_result: int,
        enable_new_behavior,
    ):
        now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        first_mhp = MemberHealthPlanFactory.create(
            plan_start_at=now,
            plan_end_at=now + datetime.timedelta(days=365),
        )
        second_mhp = MemberHealthPlanFactory.create(
            member_id=first_mhp.member_id,
            reimbursement_wallet_id=first_mhp.reimbursement_wallet_id,
            reimbursement_wallet=first_mhp.reimbursement_wallet,
            plan_start_at=now + datetime.timedelta(days=365 * 3),
            plan_end_at=None,
        )
        effective_date = now + datetime.timedelta(**effective_date_adjustment)
        expected_result_translation = {
            0: None,
            1: first_mhp,
            2: second_mhp,
        }  # TODO: break these out into fixtures

        assert (
            health_plan_repo.get_member_plan_by_wallet_and_member_id(
                member_id=first_mhp.member_id,
                wallet_id=first_mhp.reimbursement_wallet_id,
                effective_date=effective_date,
            )
            == expected_result_translation[expected_result]
        )

    @pytest.mark.parametrize(
        "effective_date_adjustment, expected_result",
        [
            pytest.param({"days": -10}, False, id="before start date"),
            pytest.param({"days": 0}, True, id="exactly equal to start date"),
            pytest.param({"days": 10}, True, id="during the plan"),
            pytest.param({"days": 365}, True, id="exactly equal to the end date"),
            pytest.param({"days": 365 * 2}, False, id="after the plan"),
        ],
    )
    def test_get_employer_plan_by_wallet_and_member_id(
        self,
        health_plan_repo,
        effective_date_adjustment: dict,
        expected_result,
        enable_new_behavior,
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        expected_ehp = EmployerHealthPlanFactory.create()
        mhp = MemberHealthPlanFactory.create(
            employer_health_plan=expected_ehp,
            reimbursement_wallet__reimbursement_organization_settings=expected_ehp.reimbursement_organization_settings,
            plan_start_at=start_date,
            plan_end_at=start_date + datetime.timedelta(days=365),
        )
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        ehp = health_plan_repo.get_employer_plan_by_wallet_and_member_id(
            member_id=mhp.member_id,
            wallet_id=mhp.reimbursement_wallet_id,
            effective_date=effective_date,
        )
        assert ehp == (expected_ehp if expected_result is True else None)

    @pytest.mark.parametrize(
        "effective_date_adjustment",
        [
            pytest.param({"days": -10}, id="before start date"),
            pytest.param({"days": 0}, id="exactly equal to start date"),
            pytest.param({"days": 10}, id="during the plan"),
            pytest.param({"days": 365}, id="exactly equal to the end date"),
            pytest.param({"days": 365 * 2}, id="after the plan"),
        ],
    )
    def test_logging_behavior_employer_plan(
        self, health_plan_repo, effective_date_adjustment: dict, enable_logging_behavior
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        expected_ehp = EmployerHealthPlanFactory.create()
        mhp = MemberHealthPlanFactory.create(
            employer_health_plan=expected_ehp,
            reimbursement_wallet__reimbursement_organization_settings=expected_ehp.reimbursement_organization_settings,
            plan_start_at=start_date,
            plan_end_at=start_date + datetime.timedelta(days=365),
        )
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        ehp = health_plan_repo.get_employer_plan_by_wallet_and_member_id(
            member_id=mhp.member_id,
            wallet_id=mhp.reimbursement_wallet_id,
            effective_date=effective_date,
        )
        assert ehp == expected_ehp

    def test_get_all_plans_for_multiple_dates(
        self, health_plan_repo, enable_new_behavior
    ):
        now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        first_mhp = MemberHealthPlanFactory.create(
            plan_start_at=now,
            plan_end_at=now + datetime.timedelta(days=365),
        )
        second_mhp = MemberHealthPlanFactory.create(
            member_id=first_mhp.member_id,
            reimbursement_wallet_id=first_mhp.reimbursement_wallet_id,
            reimbursement_wallet=first_mhp.reimbursement_wallet,
            plan_start_at=now + datetime.timedelta(days=365 * 3),
            plan_end_at=None,
        )

        result = health_plan_repo.get_all_plans_for_multiple_dates(
            member_id=first_mhp.member_id,
            wallet_id=first_mhp.reimbursement_wallet_id,
            all_dates=[
                now + datetime.timedelta(days=25),
            ],
        )
        assert result == [first_mhp]

        result = health_plan_repo.get_all_plans_for_multiple_dates(
            member_id=first_mhp.member_id,
            wallet_id=first_mhp.reimbursement_wallet_id,
            all_dates=[
                now + datetime.timedelta(days=25),
                now + datetime.timedelta(days=(365 * 3) + 25),
            ],
        )
        assert result == [first_mhp, second_mhp]

    def test_logging_behavior_get_all_plans_for_multiple_dates(
        self, health_plan_repo, enable_logging_behavior
    ):
        now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        first_mhp = MemberHealthPlanFactory.create(
            plan_start_at=now,
            plan_end_at=now + datetime.timedelta(days=365),
        )
        second_mhp = MemberHealthPlanFactory.create(
            member_id=first_mhp.member_id,
            reimbursement_wallet_id=first_mhp.reimbursement_wallet_id,
            reimbursement_wallet=first_mhp.reimbursement_wallet,
            plan_start_at=now + datetime.timedelta(days=365 * 3),
            plan_end_at=None,
        )

        result = health_plan_repo.get_all_plans_for_multiple_dates(
            member_id=first_mhp.member_id,
            wallet_id=first_mhp.reimbursement_wallet_id,
            all_dates=[
                now + datetime.timedelta(days=25),
            ],
        )
        # Without dates, this returns all member health plans for a user.
        assert result == [first_mhp, second_mhp]

        result = health_plan_repo.get_all_plans_for_multiple_dates(
            member_id=first_mhp.member_id,
            wallet_id=first_mhp.reimbursement_wallet_id,
            all_dates=[
                now + datetime.timedelta(days=25),
                now + datetime.timedelta(days=(365 * 3) + 25),
            ],
        )
        assert result == [first_mhp, second_mhp]

    def test_get_all_wallet_ids_for_an_employer_plan(self, health_plan_repo):
        ehp1, ehp2 = EmployerHealthPlanFactory.create_batch(size=2)
        mhp1a, mhp1b = MemberHealthPlanFactory.create_batch(
            size=2,
            employer_health_plan=ehp1,
            reimbursement_wallet__reimbursement_organization_settings=ehp1.reimbursement_organization_settings,
        )
        # add a second member health plan to an existing wallet -- the wallet id should still only show once
        MemberHealthPlanFactory.create(
            employer_health_plan=ehp2,
            reimbursement_wallet=mhp1b.reimbursement_wallet,
            member_id=mhp1b.member_id + 1,  # fake member id, corresponds to nothing
        )
        # add a plan that should not show
        mhp2 = MemberHealthPlanFactory.create(
            employer_health_plan=ehp2,
            reimbursement_wallet__reimbursement_organization_settings=ehp2.reimbursement_organization_settings,
        )
        expected_wallet_ids = [
            mhp1a.reimbursement_wallet_id,
            mhp1b.reimbursement_wallet_id,
        ]

        wallet_ids = health_plan_repo.get_all_wallet_ids_for_an_employer_plan(
            employer_plan_id=ehp1.id
        )
        assert wallet_ids == expected_wallet_ids
        assert mhp2.reimbursement_wallet_id not in wallet_ids

    @pytest.mark.parametrize(
        "effective_date_adjustment, expected_result",
        [
            pytest.param({"days": -10}, False, id="before start date"),
            pytest.param({"days": 0}, True, id="exactly equal to start date"),
            pytest.param({"days": 10}, True, id="during the plan"),
            pytest.param({"days": 365}, True, id="exactly equal to the end date"),
            pytest.param({"days": 365 * 2}, False, id="after the plan"),
        ],
    )
    def test_has_member_health_plan_by_wallet_and_member_id(
        self,
        health_plan_repo,
        effective_date_adjustment: dict,
        expected_result,
        enable_new_behavior,
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        mhp = MemberHealthPlanFactory.create(
            plan_start_at=start_date,
            plan_end_at=start_date + datetime.timedelta(days=365),
        )
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        res = health_plan_repo.has_member_health_plan_by_wallet_and_member_id(
            member_id=mhp.member_id,
            wallet_id=mhp.reimbursement_wallet_id,
            effective_date=effective_date,
        )
        assert res is expected_result

    @pytest.mark.parametrize(
        "effective_date_adjustment, expected_result",
        [
            pytest.param({"days": -10}, False, id="before start date"),
            pytest.param({"days": 0}, True, id="exactly equal to start date"),
            pytest.param({"days": 10}, True, id="during the plan"),
            pytest.param({"days": 365}, True, id="exactly equal to the end date"),
            pytest.param({"days": 365 * 2}, False, id="after the plan"),
        ],
    )
    def test_get_member_plan_by_demographics(
        self,
        health_plan_repo,
        effective_date_adjustment: dict,
        expected_result,
        enable_new_behavior,
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        mhp = MemberHealthPlanFactory.create(
            plan_start_at=start_date,
            plan_end_at=start_date + datetime.timedelta(days=365),
        )
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        # factory defaults
        res = health_plan_repo.get_member_plan_by_demographics(
            subscriber_last_name="paul",
            subscriber_id="abcdefg",
            patient_first_name="lucia",
            patient_last_name="paul",
            effective_date=effective_date,
        )
        assert res == (mhp if expected_result is True else None)

    @pytest.mark.parametrize(
        "effective_date_adjustment",
        [
            pytest.param({"days": -10}, id="before start date"),
            pytest.param({"days": 0}, id="exactly equal to start date"),
            pytest.param({"days": 10}, id="during the plan"),
            pytest.param({"days": 365}, id="exactly equal to the end date"),
            pytest.param({"days": 365 * 2}, id="after the plan"),
        ],
    )
    def test_logging_behavior_get_member_plan_by_demographics(
        self, health_plan_repo, effective_date_adjustment, enable_logging_behavior
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        mhp = MemberHealthPlanFactory.create(
            plan_start_at=start_date,
            plan_end_at=start_date + datetime.timedelta(days=365),
        )
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        # factory defaults
        res = health_plan_repo.get_member_plan_by_demographics(
            subscriber_last_name="paul",
            subscriber_id="abcdefg",
            patient_first_name="lucia",
            patient_last_name="paul",
            effective_date=effective_date,
        )

        # when logging, all results should be the same.
        assert res == mhp

    @pytest.mark.parametrize(
        "effective_date_adjustment, expected_result",
        [
            pytest.param({"days": -10}, False, id="before start date"),
            pytest.param({"days": 0}, True, id="exactly equal to start date"),
            pytest.param({"days": 10}, True, id="during the plan"),
            pytest.param({"days": 365}, True, id="exactly equal to the end date"),
            pytest.param({"days": 365 * 2}, False, id="after the plan"),
        ],
    )
    def test_get_family_member_plan_effective_date_effective_date(
        self,
        health_plan_repo,
        effective_date_adjustment: dict,
        expected_result,
        enable_logging_behavior,
    ):
        start_date = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        MemberHealthPlanFactory.create(
            plan_start_at=start_date,
            plan_end_at=start_date + datetime.timedelta(days=365),
        )
        effective_date = start_date + datetime.timedelta(**effective_date_adjustment)

        # factory defaults
        res = health_plan_repo.get_family_member_plan_effective_date(
            subscriber_id="abcdefg",
            effective_date=effective_date,
        )
        assert res is None

    def test_create_member_health_plan(
        self, health_plan_repo, create_health_plan, basic_qualified_wallet
    ):
        employer_health_plan = EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        )
        mhp = create_health_plan(
            employer_health_plan.id,
            basic_qualified_wallet.user_id,
            basic_qualified_wallet.id,
            datetime.datetime(2024, 1, 1),
            datetime.datetime(2024, 12, 1),
        )
        health_plan_repo.session.commit()
        retrieved = health_plan_repo.get_member_plan_by_wallet_and_member_id(
            wallet_id=mhp.reimbursement_wallet_id,
            member_id=mhp.member_id,
            effective_date=datetime.date(2024, 6, 15),
        )
        # a few trivial assertions
        assert mhp
        assert retrieved == mhp

    @pytest.mark.parametrize(
        argnames="plan_start_at, plan_end_at, emp_plan_id_offset",
        argvalues=[
            pytest.param(
                datetime.datetime(2024, 1, 1),
                datetime.datetime(2022, 1, 1),
                0,
                id="1. Member plan starts after it ends",
            ),
            pytest.param(
                datetime.datetime(2024, 1, 1),
                datetime.datetime(2024, 12, 1),
                1,
                id="2. Employer plan does not exist.",
            ),
            pytest.param(
                datetime.datetime(2024, 1, 1),
                datetime.datetime(2054, 12, 1),
                0,
                id="3. Invalid member plan end date - member plan ends after the employer plan does.",
            ),
            pytest.param(
                datetime.datetime(1024, 1, 1),
                datetime.datetime(2024, 12, 1),
                0,
                id="4. Invalid member plan start date - member plan starts before the employer plan does.",
            ),
            pytest.param(
                datetime.datetime(1024, 1, 1),
                datetime.datetime(3024, 12, 1),
                0,
                id="4. Both plan start and plan end dates are invalid",
            ),
        ],
    )
    def test_create_member_health_plan_failure(
        self,
        health_plan_repo,
        basic_qualified_wallet,
        create_health_plan,
        plan_start_at,
        plan_end_at,
        emp_plan_id_offset,
    ):
        employer_health_plan = EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        )
        _ = create_health_plan(
            employer_health_plan.id + emp_plan_id_offset,
            basic_qualified_wallet.user_id,
            basic_qualified_wallet.id,
            plan_start_at,
            plan_end_at,
        )
        with pytest.raises(ValueError):
            health_plan_repo.session.commit()

    @pytest.mark.parametrize(
        argnames="inp_subscriber_id, subscriber_id, is_subscriber_list, start_end_offset, inp_start_end_offset, exp_index",
        argvalues=[
            pytest.param(
                "1001",
                "1000",
                [True],
                [(0, 0)],
                (0, 0),
                None,
                id="0. One plan in the table. It's not the subscriber.",
            ),
            pytest.param(
                "1000",
                "1000",
                [True],
                [(0, 0)],
                (0, 0),
                0,
                id="1. One plan in the table. It's the subscriber.",
            ),
            pytest.param(
                "1000",
                "1000",
                [False],
                [(0, 0)],
                (0, 0),
                None,
                id="2. One plan in the table. It's not the subscriber.",
            ),
            pytest.param(
                "1000",
                "1000",
                [False, True],
                [(10, -10), (10, -10)],
                (0, 0),
                1,
                id="3. Two plans in the table. Second is the subscriber.",
            ),
            pytest.param(
                "1000",
                "1000",
                [True, False],
                [(10, -10), (10, -10)],
                (0, 0),
                0,
                id="4. Two plans in the table. First is the subscriber.",
            ),
            pytest.param(
                "1000",
                "1000",
                [False, False],
                [(10, -10), (10, -10)],
                (0, 0),
                None,
                id="5. Two plans in the table. Neither is the subscriber.",
            ),
            pytest.param(
                "1000",
                "1000",
                [True, False],
                [(10, -10), (10, -10)],
                (20, 0),
                None,
                id="6. Two plans in the table. One is the subscriber but falls outside the start time",
            ),
            pytest.param(
                "1000",
                "1000",
                [True, False],
                [(10, -10), (10, -10)],
                (0, -20),
                None,
                id="7. Two plans in the table. One is the subscriber but falls outside the end time",
            ),
        ],
    )
    def test_get_subscriber_member_health_plan(
        self,
        health_plan_repo,
        db,
        enable_new_behavior,
        inp_subscriber_id,
        subscriber_id,
        is_subscriber_list,
        start_end_offset,
        inp_start_end_offset,
        exp_index,
    ):
        new_ehp: EmployerHealthPlan = EmployerHealthPlanFactory.create(
            start_date=(datetime.date(2024, 1, 1)),
            end_date=(datetime.date(2024, 12, 31)),
        )
        exp = None
        to_datetime = lambda date, offset: datetime.datetime.fromordinal(
            (date + datetime.timedelta(days=offset)).toordinal()
        )
        for i, is_subscriber in enumerate(is_subscriber_list):
            plan_start_at = to_datetime(new_ehp.start_date, start_end_offset[0][0])
            plan_end_at = to_datetime(new_ehp.end_date, start_end_offset[0][1])

            new_mhp = MemberHealthPlanFactory.create(
                is_subscriber=is_subscriber,
                subscriber_insurance_id=subscriber_id,
                employer_health_plan=new_ehp,
                reimbursement_wallet__reimbursement_organization_settings=new_ehp.reimbursement_organization_settings,
                plan_start_at=plan_start_at,
                plan_end_at=plan_end_at,
            )
            if i == exp_index:
                exp = new_mhp

            db.session.expire(new_ehp)
            db.session.expire(
                new_mhp
            )  # prevent the factory from putting a different datetime format in the session

        inp_start_date = to_datetime(new_ehp.start_date, inp_start_end_offset[0])
        inp_end_date = to_datetime(new_ehp.end_date, inp_start_end_offset[1])

        res = health_plan_repo.get_subscriber_member_health_plan(
            subscriber_id=inp_subscriber_id,
            employer_health_plan_id=new_ehp.id,
            plan_start_at_earliest=inp_start_date,
            plan_end_at_latest=inp_end_date,
        )

        assert res == exp

    def test_get_subscriber_member_error(
        self,
        health_plan_repo,
        db,
        enable_new_behavior,
    ):
        new_ehp: EmployerHealthPlan = EmployerHealthPlanFactory.create(
            start_date=(datetime.date(2025, 1, 1)),
            end_date=(datetime.date(2025, 12, 31)),
        )
        to_datetime = lambda date, offset: datetime.datetime.fromordinal(
            (date + datetime.timedelta(days=offset)).toordinal()
        )
        for _ in range(0, 2):
            new_mhp = MemberHealthPlanFactory.create(
                is_subscriber=True,
                subscriber_insurance_id="1000",
                employer_health_plan=new_ehp,
                reimbursement_wallet__reimbursement_organization_settings=new_ehp.reimbursement_organization_settings,
                plan_start_at=(to_datetime(new_ehp.start_date, 0)),
                plan_end_at=(to_datetime(new_ehp.end_date, 0)),
            )

            db.session.expire(new_ehp)
            db.session.expire(
                new_mhp
            )  # prevent the factory from putting a different datetime format in the session
        with pytest.raises(MultipleResultsFound):
            _ = health_plan_repo.get_subscriber_member_health_plan(
                subscriber_id="1000",
                employer_health_plan_id=new_ehp.id,
                plan_start_at_earliest=to_datetime(new_ehp.start_date, 0),
                plan_end_at_latest=to_datetime(new_ehp.end_date, 0),
            )


@pytest.fixture()
def create_health_plan(health_plan_repo):
    def fn(employer_health_plan_id, user_id, wallet_id, plan_start_at, plan_end_at):
        return health_plan_repo.create_member_health_plan(
            employer_health_plan_id=employer_health_plan_id,
            reimbursement_wallet_id=wallet_id,
            member_id=user_id,
            subscriber_insurance_id="A_FAKE_VALUE",
            plan_type=FamilyPlanType.INDIVIDUAL,
            is_subscriber=True,
            subscriber_first_name="SFN",
            subscriber_last_name="SLN",
            subscriber_date_of_birth=datetime.date(2000, 1, 2),
            patient_first_name="PFN",
            patient_last_name="PLN",
            patient_date_of_birth=datetime.date(2002, 3, 4),
            patient_sex=MemberHealthPlanPatientSex.MALE,
            patient_relationship=MemberHealthPlanPatientRelationship.OTHER,
            plan_start_at=plan_start_at,
            plan_end_at=plan_end_at,
        )

    return fn
