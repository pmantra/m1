import json
from unittest import mock

from flask_sqlalchemy import SQLAlchemy

from authn.models.user import User
from mpractice.models.appointment import MPracticeMember
from mpractice.repository.mpractice_member import MPracticeMemberRepository
from pytests.db_util import enable_db_performance_warnings


class TestMPracticeMemberRepository:
    def test_get_member_by_user_id_no_data(
        self, db: SQLAlchemy, mpractice_member_repo: MPracticeMemberRepository
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = mpractice_member_repo.get_member_by_id(member_id=404)
            assert result is None

    def test_get_member_by_user_id_with_data(
        self,
        db: SQLAlchemy,
        mpractice_member_repo: MPracticeMemberRepository,
        member_user: User,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=5):
            result = mpractice_member_repo.get_member_by_id(member_user.id)
            expected = MPracticeMember(
                id=member_user.id,
                first_name="Alice",
                last_name="Johnson",
                email="alice.johnson@test.com",
                created_at=member_user.created_at,
                health_profile_json=json.dumps(member_user.health_profile.json),
                care_plan_id=9,
                dosespot=mock.ANY,
                phone_number="tel:+1-212-555-1515",
                subdivision_code="US-NY",
                state_name="New York",
                state_abbreviation="NY",
                country_code="US",
                address_count=1,
            )
            assert result == expected
