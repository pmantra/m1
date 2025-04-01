import datetime
from typing import Optional

import pytest
import sqlalchemy.exc

from wallet.models.reimbursement_wallet import (
    MemberHealthPlan,
    has_valid_member_plan_dates,
    has_valid_member_plan_start_date,
)
from wallet.pytests.factories import EmployerHealthPlanFactory, MemberHealthPlanFactory
from wallet.repository.health_plan import HealthPlanRepository


@pytest.mark.parametrize(
    "adjust_start_at,adjust_end_at,expected_result",
    [
        pytest.param(
            {"days": 1},
            {"days": 1},
            False,
            id="starts during existing plan, ends after",
        ),
        pytest.param(
            {"days": -1},
            {"days": -1},
            False,
            id="starts before existing plan, ends during",
        ),
        pytest.param(
            {"days": -1},
            {"days": 1},
            False,
            id="starts before and ends after existing plan",
        ),
        pytest.param(
            {"days": 1}, {"days": -1}, False, id="starts after and ends during"
        ),
        pytest.param({"days": 0}, {"days": 0}, False, id="equal dates"),
        pytest.param(
            {"days": 365},
            {"days": 367 * 2},
            True,
            id="starts exactly at the end, ends after",
        ),
        pytest.param(
            {"days": -367 * 2},
            {"days": -365},
            True,
            id="starts before, ends exactly at the start",
        ),
        pytest.param(
            {"days": 367}, {"days": 367 * 2}, True, id="starts after and ends after"
        ),
        pytest.param(
            {"days": -367}, {"days": -367 * 2}, True, id="starts before and ends before"
        ),
    ],
)
def test_member_plan_dates(
    db,
    basic_qualified_wallet,
    adjust_start_at: dict,
    adjust_end_at: dict,
    expected_result: bool,
):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    mhp = MemberHealthPlanFactory.create(
        reimbursement_wallet=basic_qualified_wallet,
        employer_health_plan=EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        ),
        plan_start_at=now,
        plan_end_at=now + datetime.timedelta(days=365),
    )
    # proposed dates for a second member health plan
    start_date = mhp.plan_start_at + datetime.timedelta(**adjust_start_at)
    start_date.replace(microsecond=0)
    end_date = mhp.plan_end_at + datetime.timedelta(**adjust_end_at)
    end_date.replace(microsecond=0)

    # works for the sqlalchemy validation
    sqlalchemy_is_valid_res = has_valid_member_plan_dates(
        member_id=mhp.member_id,
        wallet_id=mhp.reimbursement_wallet_id,
        start_at=start_date,
        end_at=end_date,
    )
    # works for the repository validation
    repo = HealthPlanRepository(session=db.session)
    raw_is_valid_res = repo.has_valid_member_plan_dates(
        member_id=mhp.member_id,
        wallet_id=mhp.reimbursement_wallet_id,
        start_at=start_date,
        end_at=end_date,
    )

    assert sqlalchemy_is_valid_res == raw_is_valid_res
    assert sqlalchemy_is_valid_res == expected_result, (
        f"Unexpected result {sqlalchemy_is_valid_res}, expected {expected_result} "
        f"for plan start {mhp.plan_start_at} and start date {start_date} "
        f"and plan end {mhp.plan_end_at} and end date {end_date}"
    )


@pytest.mark.parametrize(
    "adjust_start_at, adjust_end_at, expected_result",
    [
        pytest.param(
            {"days": -367 * 2}, {"days": -367}, True, id="starts before and ends before"
        ),
        pytest.param(
            {"days": 0},
            {"days": 10},
            False,
            id="starts at the same time as an open-ended plan",
        ),
        pytest.param(
            {"days": 1}, {"days": 366}, False, id="starts during an open-ended plan"
        ),
    ],
)
def test_member_plan_dates_for_an_open_ended_plan(
    db,
    basic_qualified_wallet,
    adjust_start_at: dict,
    adjust_end_at: dict,
    expected_result: bool,
):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    mhp = MemberHealthPlanFactory.create(
        reimbursement_wallet=basic_qualified_wallet,
        employer_health_plan=EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        ),
        plan_start_at=now,
        plan_end_at=None,
    )
    # proposed dates for a second member health plan
    start_date = now + datetime.timedelta(**adjust_start_at)
    start_date.replace(microsecond=0)
    end_date = now + datetime.timedelta(**adjust_end_at)
    end_date.replace(microsecond=0)

    # works for the sqlalchemy validation
    sqlalchemy_is_valid_res = has_valid_member_plan_dates(
        member_id=mhp.member_id,
        wallet_id=mhp.reimbursement_wallet_id,
        start_at=start_date,
        end_at=end_date,
    )
    # works for the repository validation
    repo = HealthPlanRepository(session=db.session)
    raw_is_valid_res = repo.has_valid_member_plan_dates(
        member_id=mhp.member_id,
        wallet_id=mhp.reimbursement_wallet_id,
        start_at=start_date,
        end_at=end_date,
    )

    assert sqlalchemy_is_valid_res == raw_is_valid_res
    assert sqlalchemy_is_valid_res is expected_result


@pytest.mark.parametrize(
    "adjust_start_at,plan_end_at,expected_result",
    [
        pytest.param(
            {"days": 1},
            False,
            False,
            id="cannot have two open-ended plans, after",
        ),
        pytest.param(
            {"days": -365},
            False,
            False,
            id="cannot have two open-ended plans, before",
        ),
        pytest.param(
            {"days": 0},
            False,
            False,
            id="cannot have two open-ended plans, even with equal start dates",
        ),
        pytest.param(
            {"days": -367},
            True,
            False,
            id="Cannot have an open-ended plan before a close-ended plan",
        ),
        pytest.param(
            {"days": 1},
            True,
            False,
            id="starts during an existing plan",
        ),
        pytest.param(
            {"days": 367},
            True,
            True,
            id="Can start after a close-ended plan",
        ),
    ],
)
def test_member_plan_start_date(
    db,
    basic_qualified_wallet,
    adjust_start_at: dict,
    plan_end_at: Optional[datetime.datetime],
    expected_result: bool,
):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    mhp = MemberHealthPlanFactory.create(
        reimbursement_wallet=basic_qualified_wallet,
        employer_health_plan=EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        ),
        plan_start_at=now,
        plan_end_at=None
        if plan_end_at is False
        else now + datetime.timedelta(days=365),
    )
    start_date = now + datetime.timedelta(**adjust_start_at)

    # works for the sqlalchemy validation
    sqlalchemy_is_valid_res = has_valid_member_plan_start_date(
        member_id=mhp.member_id,
        wallet_id=mhp.reimbursement_wallet_id,
        start_at=start_date,
    )
    # works for the repository validation
    repo = HealthPlanRepository(session=db.session)
    raw_is_valid_res = repo.has_valid_member_plan_start_date(
        member_id=mhp.member_id,
        wallet_id=mhp.reimbursement_wallet_id,
        start_at=start_date,
    )

    assert sqlalchemy_is_valid_res == raw_is_valid_res
    assert sqlalchemy_is_valid_res == expected_result, (
        f"Unexpected result {sqlalchemy_is_valid_res}, expected {expected_result} "
        f"for plan start {mhp.plan_start_at} and start date {start_date}"
    )


def test_create_all_null_plan_dates(db, basic_qualified_wallet):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    mhp = MemberHealthPlanFactory.create(
        reimbursement_wallet=basic_qualified_wallet,
        employer_health_plan=EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        ),
        plan_start_at=now,
        plan_end_at=now + datetime.timedelta(days=365),
    )
    new_mhp = MemberHealthPlanFactory.build(
        member_id=mhp.member_id,
        reimbursement_wallet=basic_qualified_wallet,
        employer_health_plan=EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        ),
        plan_start_at=None,
        plan_end_at=None,
    )
    db.session.add(new_mhp)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.session.commit()


def test_update_a_plan(db, basic_qualified_wallet):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    mhp = MemberHealthPlanFactory.create(
        reimbursement_wallet=basic_qualified_wallet,
        employer_health_plan=EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings
        ),
        plan_start_at=now,
        plan_end_at=now + datetime.timedelta(days=365),
    )
    new_end_at = now + datetime.timedelta(days=60)

    mhp.plan_end_at = new_end_at
    db.session.add(mhp)
    db.session.commit()
    refreshed_mhp = MemberHealthPlan.query.get(mhp.id)
    assert refreshed_mhp.plan_end_at == new_end_at
