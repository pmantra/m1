from __future__ import annotations

from datetime import datetime
from typing import List
from unittest.mock import MagicMock

import pytest

from appointments.models.constants import PRIVACY_CHOICES
from authn.models.user import User
from geography import Country
from models.enterprise import Organization
from mpractice.error import MissingMemberError, MissingPractitionerError
from mpractice.models.appointment import (
    MPracticeMember,
    MPracticePractitioner,
    ProviderAppointment,
    ProviderAppointmentForList,
    Vertical,
)
from mpractice.models.common import Pagination
from mpractice.models.translated_appointment import (
    SessionMetaInfo,
    TranslatedMPracticeMember,
    TranslatedMPracticePractitioner,
    TranslatedProviderAppointment,
    TranslatedProviderAppointmentForList,
)
from mpractice.models.translated_note import (
    MPracticeProviderAddendaAndQuestionnaire,
    StructuredInternalNote,
)
from mpractice.service.provider_appointment import ProviderAppointmentService


class TestProviderAppointmentService:
    def test_get_provider_appointments_returns_empty_result(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_provider_appointment_for_list_repo: MagicMock,
    ):
        mock_provider_appointment_for_list_repo.get_paginated_appointments_with_total_count.return_value = (
            [],
            0,
        )
        (appts, pagination) = provider_appointment_service.get_provider_appointments({})
        assert appts == []
        assert pagination == Pagination(
            limit=5, offset=0, total=0, order_direction="asc"
        )

    def test_get_provider_appointments_returns_non_empty_result(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_provider_appointment_for_list_repo: MagicMock,
        base_appointment_for_list,
    ):
        mock_provider_appointment_for_list_repo.get_paginated_appointments_with_total_count.return_value = (
            [base_appointment_for_list],
            3,
        )
        post_session = SessionMetaInfo(
            created_at=datetime(2024, 1, 2, 10, 0, 0), notes="test notes", draft=True
        )
        mock_provider_appointment_for_list_repo.get_appointment_id_to_latest_post_session_note.return_value = {
            base_appointment_for_list.id: post_session
        }
        args = {
            "practitioner_id": base_appointment_for_list.practitioner_id,
            "limit": 1,
            "offset": 0,
            "order_direction": "asc",
        }
        (appts, pagination) = provider_appointment_service.get_provider_appointments(
            args
        )
        translated_provider_appointment_for_list = TranslatedProviderAppointmentForList(
            id=997948365,
            appointment_id=1,
            scheduled_start=datetime(2024, 1, 1, 10, 0, 0),
            scheduled_end=datetime(2024, 1, 1, 11, 0, 0),
            member=TranslatedMPracticeMember(
                id=2, name="alice johnson", first_name="alice"
            ),
            repeat_patient=False,
            state="PAYMENT_PENDING",
            privacy="full_access",
            privilege_type="standard",
            rescheduled_from_previous_appointment_time=datetime(2023, 12, 1, 10, 0, 0),
            cancelled_at=None,
            post_session=post_session,
        )
        assert appts == [translated_provider_appointment_for_list]
        assert pagination == Pagination(
            limit=1, offset=0, total=3, order_direction="asc"
        )

    def test_get_provider_appointment_by_id_returns_empty_result(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_provider_appointment_repo: MagicMock,
        default_user,
    ):
        mock_provider_appointment_repo.get_appointment_by_id.return_value = None
        result = provider_appointment_service.get_provider_appointment_by_id(
            appointment_id=404, user=default_user
        )
        assert result is None

    def test_get_provider_appointment_by_id_returns_non_empty_result(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_provider_appointment_repo: MagicMock,
        mock_mpractice_member_repo: MagicMock,
        mock_mpractice_practitioner_repo: MagicMock,
        mock_note_service: MagicMock,
        mock_track_selection_service: MagicMock,
        provider_appointment_100: ProviderAppointment,
        mpractice_member: MPracticeMember,
        mpractice_practitioner: MPracticePractitioner,
        ca_vertical: Vertical,
        structured_internal_note: StructuredInternalNote,
        provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
        post_session_note: SessionMetaInfo,
        translated_provider_appointment_100: TranslatedProviderAppointment,
        default_user,
    ):
        # mock appointment data
        mock_provider_appointment_repo.get_appointment_by_id.return_value = (
            provider_appointment_100
        )
        # mock post session note
        mock_provider_appointment_repo.get_latest_post_session_note.return_value = (
            post_session_note
        )
        # mock member data
        mock_mpractice_member_repo.get_member_by_id.return_value = mpractice_member
        # mock practitioner data
        mock_mpractice_practitioner_repo.get_practitioner_by_id.return_value = (
            mpractice_practitioner
        )
        mock_mpractice_practitioner_repo.get_practitioner_subdivision_codes.return_value = [
            "US-NY"
        ]
        mock_mpractice_practitioner_repo.get_practitioner_verticals.return_value = [
            ca_vertical
        ]
        mock_mpractice_practitioner_repo.get_practitioner_states.return_value = ["NY"]
        # mock note data
        mock_note_service.get_structured_internal_note.return_value = (
            structured_internal_note
        )
        mock_note_service.get_provider_addenda_and_questionnaire.return_value = (
            provider_addenda_and_questionnaire
        )
        # mock organization data
        mock_track_selection_service.get_organization_for_user.return_value = (
            Organization(name="test org", education_only=False, rx_enabled=True)
        )

        result = provider_appointment_service.get_provider_appointment_by_id(
            appointment_id=100,
            user=default_user,
        )
        assert result == translated_provider_appointment_100

    def test_get_provider_appointment_by_id_raises_missing_member_error(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_provider_appointment_repo: MagicMock,
        mock_mpractice_member_repo: MagicMock,
        provider_appointment_100: ProviderAppointment,
        default_user,
    ):
        mock_provider_appointment_repo.get_appointment_by_id.return_value = (
            provider_appointment_100
        )
        mock_mpractice_member_repo.get_member_by_id.return_value = None
        with pytest.raises(MissingMemberError):
            provider_appointment_service.get_provider_appointment_by_id(
                appointment_id=100,
                user=default_user,
            )

    def test_get_provider_appointment_by_id_raises_missing_practitioner_error(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_provider_appointment_repo: MagicMock,
        mock_mpractice_member_repo: MagicMock,
        mock_mpractice_practitioner_repo: MagicMock,
        mpractice_member: MPracticeMember,
        provider_appointment_100: ProviderAppointment,
        default_user,
    ):
        mock_provider_appointment_repo.get_appointment_by_id.return_value = (
            provider_appointment_100
        )
        mock_mpractice_member_repo.get_member_by_id.return_value = mpractice_member
        mock_mpractice_practitioner_repo.get_practitioner_by_id.return_value = None
        with pytest.raises(MissingPractitionerError):
            provider_appointment_service.get_provider_appointment_by_id(
                appointment_id=100,
                user=default_user,
            )

    def test_translate_provider_appointment(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_country_repo: MagicMock,
        mock_mpractice_practitioner_repo: MagicMock,
        mock_note_service: MagicMock,
        ca_vertical: Vertical,
        country: Country,
        provider_appointment_100: ProviderAppointment,
        post_session_note: SessionMetaInfo,
        translated_mpractice_member: TranslatedMPracticeMember,
        translated_mpractice_practitioner: TranslatedMPracticePractitioner,
        structured_internal_note: StructuredInternalNote,
        provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
        translated_provider_appointment_100: TranslatedProviderAppointment,
        default_user,
    ):
        mock_country_repo.get.return_value = country
        mock_mpractice_practitioner_repo.get_practitioner_by_id.return_value = (
            MPracticePractitioner(id=1, dosespot="{}", messaging_enabled=True)
        )
        mock_mpractice_practitioner_repo.get_practitioner_verticals.return_value = [
            ca_vertical
        ]
        mock_mpractice_practitioner_repo.get_practitioner_subdivision_codes.return_value = [
            "US-NY"
        ]
        mock_note_service.get_structured_internal_note.return_value = (
            structured_internal_note
        )
        mock_note_service.get_provider_addenda_and_questionnaire.return_value = (
            provider_addenda_and_questionnaire
        )
        mock_mpractice_practitioner_repo.get_practitioner_states.return_value = ["NY"]

        result = provider_appointment_service.translate_provider_appointment(
            user=default_user,
            appointment=provider_appointment_100,
            latest_post_session_note=post_session_note,
            translated_member=translated_mpractice_member,
            translated_practitioner=translated_mpractice_practitioner,
        )
        assert result == translated_provider_appointment_100

    def test_translate_provider_appointment_empty_post_session_note(
        self,
        provider_appointment_service: ProviderAppointmentService,
        provider_appointment_100: ProviderAppointment,
        translated_mpractice_member: TranslatedMPracticeMember,
        translated_mpractice_practitioner: TranslatedMPracticePractitioner,
        default_user,
    ):
        result = provider_appointment_service.translate_provider_appointment(
            user=default_user,
            appointment=provider_appointment_100,
            latest_post_session_note=None,
            translated_member=translated_mpractice_member,
            translated_practitioner=translated_mpractice_practitioner,
        )
        assert result.post_session == SessionMetaInfo(
            created_at=None, draft=None, notes=""
        )

    def test_translate_provider_appointment_returns_none_prescription_info_when_appointment_is_anonymous(
        self,
        provider_appointment_service: ProviderAppointmentService,
        provider_appointment_100: ProviderAppointment,
        post_session_note: SessionMetaInfo,
        translated_mpractice_member: TranslatedMPracticeMember,
        translated_mpractice_practitioner: TranslatedMPracticePractitioner,
        default_user,
    ):
        provider_appointment_100.privacy = PRIVACY_CHOICES.anonymous
        result = provider_appointment_service.translate_provider_appointment(
            user=default_user,
            appointment=provider_appointment_100,
            latest_post_session_note=post_session_note,
            translated_member=translated_mpractice_member,
            translated_practitioner=translated_mpractice_practitioner,
        )
        assert result.prescription_info is None

    def test_translate_provider_appointment_hides_member_email_for_non_ca(
        self,
        provider_appointment_service: ProviderAppointmentService,
        provider_appointment_100: ProviderAppointment,
        translated_mpractice_member: TranslatedMPracticeMember,
        translated_mpractice_practitioner: TranslatedMPracticePractitioner,
        default_user: User,
        doula_vertical: Vertical,
    ):
        translated_mpractice_practitioner.profiles.practitioner.vertical_objects = [
            doula_vertical
        ]
        result = provider_appointment_service.translate_provider_appointment(
            user=default_user,
            appointment=provider_appointment_100,
            latest_post_session_note=None,
            translated_member=translated_mpractice_member,
            translated_practitioner=translated_mpractice_practitioner,
        )
        assert result.member.email is None

    @pytest.mark.parametrize(
        argnames="latest_post_session,expected_post_session",
        argvalues=[
            (None, SessionMetaInfo(created_at=None, draft=None, notes="")),
            (
                SessionMetaInfo(
                    created_at=datetime(2024, 3, 24, 11, 0, 0),
                    notes="test notes",
                    draft=True,
                ),
                SessionMetaInfo(
                    created_at=datetime(2024, 3, 24, 11, 0, 0),
                    notes="test notes",
                    draft=True,
                ),
            ),
        ],
        ids=[
            "no_latest_post_session",
            "has_latest_post_session",
        ],
    )
    def test_translate_provider_appointment_for_list(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_country_repo: MagicMock,
        country: Country,
        latest_post_session: SessionMetaInfo | None,
        expected_post_session: SessionMetaInfo,
    ):
        mock_country_repo.get.return_value = country
        appt = ProviderAppointmentForList(
            id=1,
            scheduled_start=datetime(2024, 3, 24, 10, 0, 0),
            scheduled_end=datetime(2024, 3, 24, 10, 15, 0),
            member_id=2,
            practitioner_id=3,
            member_first_name="Alice",
            member_last_name="Johnson",
            member_country_code="UK",
            privacy="basic",
            privilege_type="standard",
            rescheduled_from_previous_appointment_time=datetime(2024, 1, 10, 10, 0, 0),
        )
        translated_appt = TranslatedProviderAppointmentForList(
            id=997948365,
            appointment_id=1,
            scheduled_start=datetime(2024, 3, 24, 10, 0, 0),
            scheduled_end=datetime(2024, 3, 24, 10, 15, 0),
            member=TranslatedMPracticeMember(
                id=2, name="Alice Johnson", first_name="Alice", country=country
            ),
            repeat_patient=False,
            state="OVERDUE",
            privacy="basic",
            privilege_type="standard",
            rescheduled_from_previous_appointment_time=datetime(2024, 1, 10, 10, 0, 0),
            cancelled_at=None,
            post_session=expected_post_session,
        )
        result = provider_appointment_service.translate_provider_appointment_for_list(
            appt, latest_post_session
        )
        assert result == translated_appt

    def test_get_translated_member_no_data(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_mpractice_member_repo: MagicMock,
        mpractice_member: MPracticeMember,
    ):
        mock_mpractice_member_repo.get_member_by_id.return_value = None
        result = provider_appointment_service.get_translated_member(
            member_id=mpractice_member.id, appointment_privacy=PRIVACY_CHOICES.basic
        )
        assert result is None

    def test_get_translated_member_when_appointment_is_not_anonymous_and_member_country_is_us(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_mpractice_member_repo: MagicMock,
        mock_track_selection_service: MagicMock,
        mpractice_member: MPracticeMember,
        translated_mpractice_member: TranslatedMPracticeMember,
    ):
        mock_mpractice_member_repo.get_member_by_id.return_value = mpractice_member
        mock_track_selection_service.get_organization_for_user.return_value = (
            Organization(name="test org", education_only=False, rx_enabled=True)
        )
        result = provider_appointment_service.get_translated_member(
            member_id=mpractice_member.id, appointment_privacy=PRIVACY_CHOICES.basic
        )
        assert result == translated_mpractice_member

    def test_get_translated_member_when_appointment_is_not_anonymous_and_member_country_is_not_us(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_country_repo: MagicMock,
        mock_mpractice_member_repo: MagicMock,
        mock_track_selection_service: MagicMock,
        country: Country,
        mpractice_member_uk: MPracticeMember,
        translated_mpractice_member_uk: TranslatedMPracticeMember,
    ):
        mock_mpractice_member_repo.get_member_by_id.return_value = mpractice_member_uk
        mock_country_repo.get.return_value = country
        mock_track_selection_service.get_organization_for_user.return_value = (
            Organization(name="test org", education_only=False, rx_enabled=True)
        )
        result = provider_appointment_service.get_translated_member(
            member_id=mpractice_member_uk.id, appointment_privacy=PRIVACY_CHOICES.basic
        )
        assert result == translated_mpractice_member_uk

    def test_get_translated_member_when_appointment_is_anonymous(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_mpractice_member_repo: MagicMock,
        mpractice_member: MPracticeMember,
        translated_mpractice_member_anonymous: TranslatedMPracticeMember,
    ):
        mock_mpractice_member_repo.get_member_by_id.return_value = mpractice_member
        result = provider_appointment_service.get_translated_member(
            member_id=mpractice_member.id, appointment_privacy=PRIVACY_CHOICES.anonymous
        )
        assert result == translated_mpractice_member_anonymous

    def test_get_translated_practitioner_no_data(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_mpractice_practitioner_repo: MagicMock,
        mpractice_practitioner: MPracticePractitioner,
    ):
        mock_mpractice_practitioner_repo.get_practitioner_by_id.return_value = None
        result = provider_appointment_service.get_translated_practitioner(
            practitioner_id=mpractice_practitioner.id
        )
        assert result is None

    def test_get_translated_practitioner_returns_expected_data(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_mpractice_practitioner_repo: MagicMock,
        mpractice_practitioner: MPracticePractitioner,
        translated_mpractice_practitioner: TranslatedMPracticePractitioner,
        ca_vertical: Vertical,
    ):
        mock_mpractice_practitioner_repo.get_practitioner_by_id.return_value = (
            mpractice_practitioner
        )
        mock_mpractice_practitioner_repo.get_practitioner_verticals.return_value = [
            ca_vertical
        ]
        mock_mpractice_practitioner_repo.get_practitioner_subdivision_codes.return_value = [
            "US-NY"
        ]
        mock_mpractice_practitioner_repo.get_practitioner_states.return_value = ["NY"]

        result = provider_appointment_service.get_translated_practitioner(
            practitioner_id=mpractice_practitioner.id
        )
        assert result == translated_mpractice_practitioner

    @pytest.mark.parametrize(
        argnames="verticals,values,certified_values",
        argvalues=[
            ([], ["val1", "val2"], ["val1", "val2"]),
            (
                [
                    Vertical(
                        id=1,
                        name="test vertical",
                        filter_by_state=False,
                        can_prescribe=False,
                    )
                ],
                ["val1", "val2"],
                [],
            ),
            (
                [
                    Vertical(
                        id=1,
                        name="test vertical",
                        filter_by_state=False,
                        can_prescribe=False,
                    ),
                    Vertical(
                        id=2,
                        name="test vertical",
                        filter_by_state=True,
                        can_prescribe=True,
                    ),
                ],
                ["val1", "val2"],
                ["val1", "val2"],
            ),
        ],
        ids=[
            "no_vertical",
            "no_vertical_can_filter_by_state",
            "at_least_one_vertical_can_filter_by_state",
        ],
    )
    def test_get_certified_values(
        self,
        provider_appointment_service: ProviderAppointmentService,
        verticals: List[Vertical],
        values: List[str],
        certified_values: List[str],
    ):
        result = provider_appointment_service.get_certified_values(
            verticals=verticals, values=values
        )
        assert result == certified_values

    @pytest.mark.parametrize(
        argnames="country_code,expected_country",
        argvalues=[
            (None, None),
            ("US", None),
            ("UK", Country(alpha_2="a2", alpha_3="a3", name="UK")),
        ],
        ids=[
            "no_country_code",
            "us_country_code",
            "non_us_country_code",
        ],
    )
    def test_get_country(
        self,
        provider_appointment_service: ProviderAppointmentService,
        mock_country_repo: MagicMock,
        country_code: str | None,
        expected_country: Country | None,
    ):
        mock_country_repo.get.return_value = expected_country
        result = provider_appointment_service.get_country(country_code=country_code)
        assert result == expected_country
