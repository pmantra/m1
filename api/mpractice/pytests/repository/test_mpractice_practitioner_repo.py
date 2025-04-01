import json

from flask_sqlalchemy import SQLAlchemy

from authn.models.user import User
from mpractice.models.appointment import MPracticePractitioner, Vertical
from mpractice.repository.mpractice_practitioner import MPracticePractitionerRepository
from pytests.db_util import enable_db_performance_warnings
from pytests.factories import PractitionerUserFactory, SubdivisionCodeFactory


class TestMPracticePractitionerRepository:
    def test_get_practitioner_by_id_no_data(
        self,
        db: SQLAlchemy,
        mpractice_practitioner_repo: MPracticePractitionerRepository,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = mpractice_practitioner_repo.get_practitioner_by_id(
                practitioner_id=404
            )
            assert result is None

    def test_get_practitioner_by_id_with_data(
        self,
        db: SQLAlchemy,
        mpractice_practitioner_repo: MPracticePractitionerRepository,
    ):
        practitioner = PractitionerUserFactory.create()
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = mpractice_practitioner_repo.get_practitioner_by_id(
                practitioner_id=practitioner.id
            )
            expected = MPracticePractitioner(
                id=practitioner.id,
                messaging_enabled=practitioner.practitioner_profile.messaging_enabled,
                first_name=practitioner.first_name,
                last_name=practitioner.last_name,
                country_code=practitioner.practitioner_profile.country_code,
                dosespot=json.dumps(practitioner.practitioner_profile.dosespot),
            )
            assert result == expected

    def test_get_practitioner_subdivision_codes_no_data(
        self,
        db: SQLAlchemy,
        mpractice_practitioner_repo: MPracticePractitionerRepository,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = mpractice_practitioner_repo.get_practitioner_subdivision_codes(
                practitioner_id=404
            )
            assert result == []

    def test_get_practitioner_subdivision_codes_with_data(
        self,
        db: SQLAlchemy,
        mpractice_practitioner_repo: MPracticePractitionerRepository,
    ):
        practitioner = PractitionerUserFactory.create()
        SubdivisionCodeFactory.create(
            practitioner_id=practitioner.id, subdivision_code="US-CT"
        )
        SubdivisionCodeFactory.create(
            practitioner_id=practitioner.id, subdivision_code="US-NJ"
        )
        SubdivisionCodeFactory.create(
            practitioner_id=practitioner.id, subdivision_code="US-NY"
        )
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = mpractice_practitioner_repo.get_practitioner_subdivision_codes(
                practitioner_id=practitioner.id
            )
            assert result == ["US-CT", "US-NJ", "US-NY"]

    def test_get_practitioner_verticals_no_data(
        self,
        db: SQLAlchemy,
        mpractice_practitioner_repo: MPracticePractitionerRepository,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = mpractice_practitioner_repo.get_practitioner_verticals(
                practitioner_id=404
            )
            assert result == []

    def test_get_practitioner_verticals_with_data(
        self,
        db: SQLAlchemy,
        mpractice_practitioner_repo: MPracticePractitionerRepository,
    ):
        practitioner = PractitionerUserFactory.create()
        verticals = practitioner.practitioner_profile.verticals
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = mpractice_practitioner_repo.get_practitioner_verticals(
                practitioner_id=practitioner.id
            )
            assert result == [
                Vertical(
                    id=verticals[0].id,
                    name=verticals[0].name,
                    can_prescribe=verticals[0].can_prescribe,
                    filter_by_state=verticals[0].filter_by_state,
                )
            ]

    def test_get_certified_states_no_data(
        self,
        mpractice_practitioner_repo: MPracticePractitionerRepository,
    ):
        result = mpractice_practitioner_repo.get_practitioner_states(
            practitioner_id=404
        )
        assert result == []

    def test_get_certified_states_returns_expected_data(
        self,
        mpractice_practitioner_repo: MPracticePractitionerRepository,
        practitioner_user: User,
    ):
        result = mpractice_practitioner_repo.get_practitioner_states(
            practitioner_id=practitioner_user.id
        )
        assert result == ["NY"]
