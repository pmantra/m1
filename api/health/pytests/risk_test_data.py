from contextlib import contextmanager
from typing import List

import pytest

from authn.models.user import User
from health.data_models.risk_flag import RiskFlag, RiskFlagSeverity
from health.models.risk_enums import RiskFlagName
from models.tracks.track import TrackName
from pytests.factories import MemberTrackFactory

# from sqlalchemy.sql import delete
# from storage.connection import db


@pytest.fixture()
def pregnancy_user(session, default_user) -> User:
    MemberTrackFactory.create(
        user=default_user,
        name=TrackName.PREGNANCY,
    )
    session.add(default_user)
    session.commit()
    return default_user


@pytest.fixture()
def fertility_user(session, default_user) -> User:
    MemberTrackFactory.create(
        user=default_user,
        name=TrackName.FERTILITY,
    )
    session.add(default_user)
    session.commit()
    return default_user


@contextmanager
def create_risk_flags_for_test(session):  # returns dictionary of name->RiskFlag
    # existing_risk_flags = session.query(RiskFlag).all()
    # existing_risk_flag_names = [r.name for r in existing_risk_flags]
    # existing_member_risk_flags = session.query(MemberRiskFlag).all()

    flags = [
        # Test Flags for each severity
        ("None", RiskFlagSeverity.NONE),
        ("None2", RiskFlagSeverity.NONE),
        ("Low", RiskFlagSeverity.LOW_RISK),
        ("Medium", RiskFlagSeverity.MEDIUM_RISK),
        ("High", RiskFlagSeverity.HIGH_RISK),
        ("High2", RiskFlagSeverity.HIGH_RISK),
        # BMI Flags
        ("Overweight", RiskFlagSeverity.LOW_RISK),
        ("Obesity", RiskFlagSeverity.MEDIUM_RISK),
        # Age Flags
        ("Advanced Maternal Age (40+)", RiskFlagSeverity.MEDIUM_RISK),
        ("Advanced Maternal Age", RiskFlagSeverity.NONE),
        # Other Flags
        ("High blood pressure - Current pregnancy", RiskFlagSeverity.HIGH_RISK),
        ("Drug use", RiskFlagSeverity.MEDIUM_RISK),
        ("Anxiety - Existing condition", RiskFlagSeverity.LOW_RISK),
        ("Anxiety - Past pregnancy", RiskFlagSeverity.MEDIUM_RISK),
        ("Anxiety - Current pregnancy", RiskFlagSeverity.HIGH_RISK),
        ("months trying to conceive", RiskFlagSeverity.NONE),
        (RiskFlagName.FIRST_TRIMESTER, RiskFlagSeverity.NONE),
        (RiskFlagName.SECOND_TRIMESTER, RiskFlagSeverity.NONE),
        (RiskFlagName.EARLY_THIRD_TRIMESTER, RiskFlagSeverity.NONE),
        (RiskFlagName.LATE_THIRD_TRIMESTER, RiskFlagSeverity.NONE),
    ]
    names = set()
    for name, severity in flags:
        flag = RiskFlag(name=name, severity=severity)
        if name in ["Advanced Maternal Age", "Advanced Maternal Age (40+)"]:
            flag.relevant_to_maternity = True
        names.add(name)
        session.add(flag)
    session.commit()

    for name in RiskFlagName:
        if name.value not in names:
            flag = RiskFlag(name=name.value, severity=RiskFlagSeverity.NONE)
            session.add(flag)
            names.add(name.value)
    session.commit()

    risk_flags: List[RiskFlag] = session.query(RiskFlag).all()
    # risk_flag_ids = [r.id for r in risk_flags]
    yield {r.name: r for r in risk_flags}
    # member_risks = (
    #     session.query(MemberRiskFlag)
    #     .filter(MemberRiskFlag.risk_flag_id.in_(risk_flag_ids))
    #     .all()
    # )
    # for member_risk in member_risks:
    #     session.delete(member_risk)
    # for risk_flag in risk_flags:
    #     session.delete(risk_flag)
    # session.commit()
    # result1 = db.session.execute(  # noqa
    #     delete(MemberRiskFlag).where(MemberRiskFlag.risk_flag_id.in_(risk_flag_ids))
    # )
    # result2 = db.session.execute(
    #     delete(RiskFlag).where(RiskFlag.id.in_(risk_flag_ids))
    # )  # noqa
    # db.session.commit()
