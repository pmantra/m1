from __future__ import annotations

import datetime
import json
from typing import List
from unittest import mock
from unittest.mock import MagicMock

import pytest

from appointments.models.appointment import Appointment
from appointments.models.reschedule_history import RescheduleHistory
from appointments.pytests.factories import PaymentAccountingEntryFactory
from authn.models.user import User
from geography import Country
from models.questionnaires import COACHING_NOTES_COACHING_PROVIDERS_OID, QuestionTypes
from models.tracks import TrackName
from mpractice.models.appointment import (
    MPracticeMember,
    MPracticePractitioner,
    ProviderAppointment,
    ProviderAppointmentForList,
    Vertical,
)
from mpractice.models.note import (
    MPracticeAnswer,
    MPracticeProviderAddendum,
    MPracticeProviderAddendumAnswer,
    MPracticeQuestion,
    MPracticeQuestionnaire,
    MPracticeQuestionSet,
    MPracticeRecordedAnswer,
    MPracticeRecordedAnswerSet,
)
from mpractice.models.translated_appointment import (
    DoseSpotPharmacyInfo,
    MemberProfile,
    Need,
    Organization,
    PractitionerProfile,
    PrescriptionInfo,
    Product,
    Profiles,
    SessionMetaInfo,
    State,
    TranslatedMPracticeMember,
    TranslatedMPracticePractitioner,
    TranslatedProviderAppointment,
)
from mpractice.models.translated_note import (
    MPracticeProviderAddendaAndQuestionnaire,
    StructuredInternalNote,
    TranslatedMPracticeAnswer,
    TranslatedMPracticeProviderAddendum,
    TranslatedMPracticeQuestion,
    TranslatedMPracticeQuestionnaire,
    TranslatedMPracticeQuestionSet,
    TranslatedMPracticeRecordedAnswer,
    TranslatedMPracticeRecordedAnswerSet,
)
from mpractice.repository.mpractice_member import MPracticeMemberRepository
from mpractice.repository.mpractice_practitioner import MPracticePractitionerRepository
from mpractice.repository.mpractice_questionnaire import (
    MPracticeQuestionnaireRepository,
)
from mpractice.repository.provider_appointment import ProviderAppointmentRepository
from mpractice.repository.provider_appointment_for_list import (
    ProviderAppointmentForListRepository,
)
from mpractice.repository.transaction import TransactionRepository
from mpractice.service.note import MPracticeNoteService
from mpractice.service.provider_appointment import ProviderAppointmentService
from pytests.factories import (
    AddressFactory,
    AppointmentFactory,
    AppointmentMetaDataFactory,
    ClientTrackFactory,
    CreditFactory,
    DefaultUserFactory,
    FeeAccountingEntryFactory,
    HealthProfileFactory,
    MemberProfileFactory,
    MemberTrackFactory,
    OrganizationFactory,
    PractitionerUserFactory,
    ProductFactory,
    RescheduleHistoryFactory,
    ScheduleEventFactory,
    StateFactory,
)


@pytest.fixture(scope="function")
def provider_appointment_repo(session) -> ProviderAppointmentRepository:
    return ProviderAppointmentRepository(session=session)


@pytest.fixture(scope="function")
def provider_appointment_for_list_repo(session) -> ProviderAppointmentForListRepository:
    return ProviderAppointmentForListRepository(session=session)


@pytest.fixture(scope="function")
def mpractice_member_repo(session) -> MPracticeMemberRepository:
    return MPracticeMemberRepository(session=session)


@pytest.fixture(scope="function")
def mpractice_practitioner_repo(session) -> MPracticePractitionerRepository:
    return MPracticePractitionerRepository(session=session)


@pytest.fixture(scope="function")
def transaction_repo(session) -> TransactionRepository:
    return TransactionRepository(session=session)


@pytest.fixture(scope="function")
def questionnaire_repo(session) -> MPracticeQuestionnaireRepository:
    return MPracticeQuestionnaireRepository(
        session=session, include_soft_deleted_question_sets=False
    )


@pytest.fixture(scope="function")
def questionnaire_repo_include_soft_deleted_question_sets(
    session,
) -> MPracticeQuestionnaireRepository:
    return MPracticeQuestionnaireRepository(
        session=session, include_soft_deleted_question_sets=True
    )


@pytest.fixture(scope="function")
def appointment_100() -> Appointment:
    appt = AppointmentFactory.create(
        id=100,
        scheduled_start=datetime.datetime(2023, 1, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 1, 1, 11, 00, 00),
    )
    AppointmentMetaDataFactory.create(
        id=101,
        appointment_id=appt.id,
        appointment=appt,
        content="metadata content 101",
        draft=True,
        created_at=datetime.datetime(2023, 1, 1, 10, 0, 0),
        modified_at=datetime.datetime(2023, 1, 1, 12, 0, 0),
    )
    AppointmentMetaDataFactory.create(
        id=102,
        appointment_id=appt.id,
        appointment=appt,
        content="metadata content 102",
        draft=True,
        created_at=datetime.datetime(2023, 2, 1, 10, 0, 0),
        modified_at=datetime.datetime(2023, 2, 2, 12, 0, 0),
    )
    # latest post session note
    AppointmentMetaDataFactory.create(
        id=103,
        appointment_id=appt.id,
        appointment=appt,
        content="metadata content 103",
        draft=False,
        created_at=datetime.datetime(2023, 2, 1, 10, 0, 0),
        modified_at=datetime.datetime(2023, 2, 2, 12, 0, 0),
    )
    PaymentAccountingEntryFactory.create(
        appointment_id=appt.id,
        amount=100,
        captured_at=datetime.datetime(2023, 1, 2, 9, 0, 0),
    )
    return appt


@pytest.fixture(scope="function")
def appointment_200() -> Appointment:
    appt = AppointmentFactory.create(
        id=200,
        scheduled_start=datetime.datetime(2023, 2, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 2, 1, 11, 00, 00),
    )
    return appt


@pytest.fixture(scope="function")
def appointment_300() -> Appointment:
    appt = AppointmentFactory.create(
        id=300,
        scheduled_start=datetime.datetime(2023, 3, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 3, 1, 11, 00, 00),
    )
    # latest post session note
    AppointmentMetaDataFactory.create(
        appointment_id=appt.id,
        appointment=appt,
        content="metadata content 301",
        draft=True,
        created_at=datetime.datetime(2023, 3, 2, 10, 00, 00),
        modified_at=datetime.datetime(2023, 3, 3, 10, 00, 00),
    )
    AppointmentMetaDataFactory.create(
        appointment_id=appt.id,
        appointment=appt,
        content="metadata content 302",
        draft=True,
        created_at=datetime.datetime(2023, 3, 2, 10, 00, 00),
        modified_at=datetime.datetime(2023, 3, 2, 10, 00, 00),
    )
    CreditFactory.create(
        id=301,
        amount=100,
        appointment_id=appt.id,
        user_id=appt.member_schedule.user_id,
        used_at=datetime.datetime(2023, 3, 2, 8, 0, 0),
    )
    CreditFactory.create(
        id=302,
        amount=250,
        appointment_id=appt.id,
        user_id=appt.member_schedule.user_id,
        used_at=datetime.datetime(2023, 3, 3, 9, 0, 0),
    )
    CreditFactory.create(
        id=303,
        amount=300,
        appointment_id=appt.id,
        user_id=appt.member_schedule.user_id,
    )
    return appt


@pytest.fixture(scope="function")
def appointment_400() -> Appointment:
    appt = AppointmentFactory.create(
        id=400,
        scheduled_start=datetime.datetime(2023, 4, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 4, 1, 11, 00, 00),
    )
    FeeAccountingEntryFactory.create(appointment_id=appt.id)
    FeeAccountingEntryFactory.create(appointment_id=appt.id)
    return appt


@pytest.fixture(scope="function")
def appointment_500(appointment_400) -> Appointment:
    return AppointmentFactory.create(
        id=500,
        scheduled_start=datetime.datetime(2023, 5, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 5, 1, 11, 00, 00),
        product=ProductFactory.create(
            id=500, practitioner=appointment_400.practitioner
        ),
        member_schedule=appointment_400.member_schedule,
    )


@pytest.fixture(scope="function")
def appointment_600(appointment_400) -> Appointment:
    return AppointmentFactory.create(
        id=600,
        scheduled_start=datetime.datetime(2023, 6, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 6, 1, 11, 00, 00),
        product=ProductFactory.create(
            id=600, practitioner=appointment_400.practitioner
        ),
        member_schedule=appointment_400.member_schedule,
    )


@pytest.fixture(scope="function")
def appointment_700(practitioner_user: User) -> Appointment:
    schedule_event = ScheduleEventFactory.create(
        schedule=practitioner_user.schedule,
        starts_at=datetime.datetime(2023, 1, 1, 0, 0, 0),
        ends_at=datetime.datetime(2024, 1, 1, 1, 0, 0),
    )
    return AppointmentFactory.create(
        id=700,
        scheduled_start=datetime.datetime(2023, 7, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 7, 1, 11, 00, 00),
        schedule_event=schedule_event,
    )


@pytest.fixture(scope="function")
def appointment_800_cancelled(appointment_700: Appointment) -> Appointment:
    return AppointmentFactory.create(
        id=800,
        scheduled_start=datetime.datetime(2023, 7, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 7, 1, 11, 00, 00),
        cancelled_at=datetime.datetime(2023, 6, 29, 10, 00, 00),
        schedule_event=appointment_700.schedule_event,
    )


@pytest.fixture(scope="function")
def reschedule_history_101(appointment_100) -> RescheduleHistory:
    return RescheduleHistoryFactory.create(id=101, appointment_id=appointment_100.id)


@pytest.fixture(scope="function")
def reschedule_history_102(appointment_100) -> RescheduleHistory:
    return RescheduleHistoryFactory.create(id=102, appointment_id=appointment_100.id)


@pytest.fixture(scope="function")
def reschedule_history_201(appointment_200) -> RescheduleHistory:
    return RescheduleHistoryFactory.create(id=201, appointment_id=appointment_200.id)


@pytest.fixture(scope="function")
def appointment_for_list_100(
    appointment_100, reschedule_history_102
) -> ProviderAppointmentForList:
    return get_expected_appointment_for_list(
        appointment=appointment_100, reschedule_history=reschedule_history_102
    )


@pytest.fixture(scope="function")
def appointment_for_list_200(
    appointment_200, reschedule_history_201
) -> ProviderAppointmentForList:
    return get_expected_appointment_for_list(
        appointment=appointment_200, reschedule_history=reschedule_history_201
    )


@pytest.fixture(scope="function")
def appointment_for_list_300(appointment_300) -> ProviderAppointmentForList:
    return get_expected_appointment_for_list(appointment=appointment_300)


@pytest.fixture(scope="function")
def appointment_for_list_400(appointment_400) -> ProviderAppointmentForList:
    return get_expected_appointment_for_list(appointment=appointment_400)


@pytest.fixture(scope="function")
def appointment_for_list_500(appointment_500) -> ProviderAppointmentForList:
    return get_expected_appointment_for_list(
        appointment=appointment_500, repeat_patient_appointment_count=1
    )


@pytest.fixture(scope="function")
def appointment_for_list_600(appointment_600) -> ProviderAppointmentForList:
    return get_expected_appointment_for_list(
        appointment=appointment_600, repeat_patient_appointment_count=2
    )


@pytest.fixture(scope="function")
def base_appointment_for_list() -> ProviderAppointmentForList:
    return ProviderAppointmentForList(
        id=1,
        scheduled_start=datetime.datetime(2024, 1, 1, 10, 0, 0),
        scheduled_end=datetime.datetime(2024, 1, 1, 11, 0, 0),
        member_started_at=datetime.datetime(2024, 1, 1, 10, 0, 0),
        member_ended_at=datetime.datetime(2024, 1, 1, 11, 0, 0),
        practitioner_started_at=datetime.datetime(2024, 1, 1, 11, 0, 0),
        practitioner_ended_at=datetime.datetime(2024, 1, 1, 11, 0, 0),
        member_id=2,
        member_first_name="alice",
        member_last_name="johnson",
        practitioner_id=3,
        privacy="full_access",
        privilege_type="standard",
        rescheduled_from_previous_appointment_time=datetime.datetime(
            2023, 12, 1, 10, 0, 0
        ),
    )


@pytest.fixture(scope="function")
def mock_country_repo() -> MagicMock:
    with mock.patch(
        "geography.repository.CountryRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_mpractice_member_repo() -> MagicMock:
    with mock.patch(
        "mpractice.repository.mpractice_member.MPracticeMemberRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_mpractice_practitioner_repo() -> MagicMock:
    with mock.patch(
        "mpractice.repository.mpractice_practitioner.MPracticePractitionerRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_provider_appointment_repo() -> MagicMock:
    with mock.patch(
        "mpractice.repository.provider_appointment.ProviderAppointmentRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_provider_appointment_for_list_repo() -> MagicMock:
    with mock.patch(
        "mpractice.repository.provider_appointment_for_list.ProviderAppointmentForListRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_track_selection_service() -> MagicMock:
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def provider_appointment_service(
    mock_country_repo: MagicMock,
    mock_mpractice_member_repo: MagicMock,
    mock_mpractice_practitioner_repo: MagicMock,
    mock_provider_appointment_repo: MagicMock,
    mock_provider_appointment_for_list_repo: MagicMock,
    mock_note_service: MagicMock,
    mock_track_selection_service: MagicMock,
) -> ProviderAppointmentService:
    return ProviderAppointmentService(
        country_repo=mock_country_repo,
        member_repo=mock_mpractice_member_repo,
        practitioner_repo=mock_mpractice_practitioner_repo,
        provider_appt_repo=mock_provider_appointment_repo,
        provider_appt_for_list_repo=mock_provider_appointment_for_list_repo,
        note_service=mock_note_service,
        track_selection_service=mock_track_selection_service,
    )


@pytest.fixture(scope="function")
def mock_provider_appointment_service_for_appointments_resource() -> MagicMock:
    with mock.patch(
        "mpractice.service.provider_appointment.ProviderAppointmentService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "mpractice.resource.provider_appointments.ProviderAppointmentService",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def mock_provider_appointment_service_for_appointment_resource() -> MagicMock:
    with mock.patch(
        "mpractice.service.provider_appointment.ProviderAppointmentService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "mpractice.resource.provider_appointment.ProviderAppointmentService",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def mock_mpractice_questionnaire_repo() -> MagicMock:
    with mock.patch(
        "mpractice.repository.mpractice_questionnaire.MPracticeQuestionnaireRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def note_service(
    mock_mpractice_questionnaire_repo,
) -> MPracticeNoteService:
    return MPracticeNoteService(questionnaire_repo=mock_mpractice_questionnaire_repo)


@pytest.fixture(scope="function")
def mock_note_service() -> MagicMock:
    with mock.patch(
        "mpractice.service.note.MPracticeNoteService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "mpractice.service.provider_appointment.MPracticeNoteService",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def practitioner_user():
    return PractitionerUserFactory.create()


@pytest.fixture(scope="function")
def member_user():
    user = DefaultUserFactory.create(
        first_name="Alice",
        last_name="Johnson",
        email="alice.johnson@test.com",
    )
    HealthProfileFactory.create(user=user, json={"birthday": "1999-02-24"})
    MemberProfileFactory.create(
        user=user,
        care_plan_id=9,
        phone_number="+12125551515",
        state=StateFactory.create(),
        country_code="US",
    )
    AddressFactory.create(user=user)
    MemberTrackFactory.create(
        user=user,
        client_track=ClientTrackFactory.create(
            organization=OrganizationFactory.create(
                id=100,
                name="test_org",
                education_only=False,
                rx_enabled=True,
            )
        ),
        name=TrackName.PREGNANCY,
    )
    return user


@pytest.fixture(scope="function")
def provider_appointment_100() -> ProviderAppointment:
    return ProviderAppointment(
        id=100,
        scheduled_start=datetime.datetime(2024, 3, 21, 10, 0, 0),
        scheduled_end=datetime.datetime(2024, 3, 21, 10, 15, 0),
        member_started_at=datetime.datetime(2024, 3, 21, 10, 0, 0),
        member_ended_at=datetime.datetime(2024, 3, 21, 10, 14, 0),
        practitioner_started_at=datetime.datetime(2024, 3, 21, 10, 0, 0),
        practitioner_ended_at=datetime.datetime(2024, 3, 21, 10, 14, 9),
        phone_call_at=datetime.datetime(2024, 3, 21, 10, 0, 1),
        practitioner_id=2,
        member_id=3,
        vertical_id=4,
        privacy="basic",
        privilege_type="standard",
        purpose="birth_planning",
        client_notes="pre-session notes",
        need_id=1,
        need_name="egg freeze",
        need_description="timeline for egg freeze",
        video='{"member_token": "mt", "practitioner_token": "pt", "session_id": "123"}',
        cancellation_policy_name="conservative",
        json=json.dumps(
            {
                "cancelled_note": "cancelled by patient",
                "rx_written_via": "dosespot",
                "member_disconnected_at": "2024-03-21T10:05:00",
                "practitioner_disconnected_at": "2024-03-21T10:05:01",
            }
        ),
    )


@pytest.fixture(scope="function")
def country() -> Country:
    return Country(alpha_2="UK", alpha_3="alpha 3", name="United Kingdom")


@pytest.fixture(scope="function")
def organization() -> Organization:
    return Organization(
        name="test org",
        education_only=False,
        rx_enabled=True,
    )


@pytest.fixture(scope="function")
def post_session_note() -> SessionMetaInfo:
    return SessionMetaInfo(
        created_at=datetime.datetime(2024, 3, 22, 10, 0, 0),
        draft=False,
        notes="post-session notes",
    )


@pytest.fixture(scope="function")
def pharmacy_info() -> DoseSpotPharmacyInfo:
    return DoseSpotPharmacyInfo(
        PharmacyId="1",
        Pharmacy="test pharma",
        State="NY",
        ZipCode="10027",
        PrimaryFax="555-555-5555",
        StoreName="999 Pharmacy",
        Address1="999 999th St",
        Address2="",
        PrimaryPhone="555-555-5556",
        PrimaryPhoneType="Work",
        City="NEW YORK",
        IsPreferred=True,
        IsDefault=False,
        ServiceLevel=9,
    )


@pytest.fixture(scope="function")
def prescription_info_not_enabled(
    pharmacy_info: DoseSpotPharmacyInfo,
) -> PrescriptionInfo:
    return PrescriptionInfo(pharmacy_id="1", pharmacy_info=pharmacy_info, enabled=False)


@pytest.fixture(scope="function")
def prescription_info_enabled(pharmacy_info: DoseSpotPharmacyInfo) -> PrescriptionInfo:
    return PrescriptionInfo(pharmacy_id="1", pharmacy_info=pharmacy_info, enabled=True)


@pytest.fixture(scope="function")
def ca_vertical() -> Vertical:
    return Vertical(
        id=1, name="Care Advocate", filter_by_state=True, can_prescribe=True
    )


@pytest.fixture(scope="function")
def doula_vertical() -> Vertical:
    return Vertical(id=2, name="Doula", filter_by_state=True, can_prescribe=True)


@pytest.fixture(scope="function")
def dosespot() -> dict:
    return {
        "global_pharmacy": {
            "pharmacy_id": "1",
            "pharmacy_info": {
                "PharmacyId": "1",
                "Pharmacy": "test pharma",
                "State": "NY",
                "ZipCode": "10027",
                "PrimaryFax": "555-555-5555",
                "StoreName": "999 Pharmacy",
                "Address1": "999 999th St",
                "Address2": "",
                "PrimaryPhone": "555-555-5556",
                "PrimaryPhoneType": "Work",
                "City": "NEW YORK",
                "IsPreferred": True,
                "IsDefault": False,
                "ServiceLevel": 9,
            },
        }
    }


@pytest.fixture(scope="function")
def mpractice_member(dosespot: dict) -> MPracticeMember:
    return MPracticeMember(
        id=2,
        first_name="Alice",
        last_name="Johnson",
        email="alice.johnson@xxx.com",
        created_at=datetime.datetime(2022, 1, 1, 0, 0, 0),
        care_plan_id=1,
        dosespot=json.dumps(dosespot),
        phone_number="+12125551515",
        subdivision_code="US-NY",
        state_abbreviation="NY",
        country_code="US",
        organization_name="test org",
        organization_education_only=False,
        organization_rx_enabled=True,
    )


@pytest.fixture(scope="function")
def mpractice_member_uk() -> MPracticeMember:
    return MPracticeMember(
        id=3,
        first_name="Bob",
        last_name="Johnson",
        email="bob.johnson@xxx.com",
        created_at=datetime.datetime(2022, 1, 1, 0, 0, 0),
        care_plan_id=1,
        dosespot="{}",
        state_abbreviation="ZZ",
        country_code="UK",
        organization_name="test org",
        organization_education_only=False,
        organization_rx_enabled=True,
    )


@pytest.fixture(scope="function")
def mpractice_practitioner() -> MPracticePractitioner:
    return MPracticePractitioner(
        id=1,
        first_name="Stephanie",
        last_name="Schmitt",
        dosespot=json.dumps({"clinic_key": "NEYg4R", "clinic_id": 370, "user_id": 482}),
        country_code="US",
        messaging_enabled=True,
    )


@pytest.fixture(scope="function")
def translated_mpractice_member(dosespot: dict) -> TranslatedMPracticeMember:
    return TranslatedMPracticeMember(
        id=2,
        first_name="Alice",
        last_name="Johnson",
        email="alice.johnson@xxx.com",
        created_at=datetime.datetime(2022, 1, 1, 0, 0, 0),
        care_plan_id=1,
        dosespot=json.dumps(dosespot),
        phone_number="+12125551515",
        subdivision_code="US-NY",
        state_abbreviation="NY",
        country_code="US",
        organization_name="test org",
        organization_education_only=False,
        organization_rx_enabled=True,
        name="Alice Johnson",
        country=None,
        organization=Organization(
            name="test org",
            education_only=False,
            rx_enabled=True,
        ),
        profiles=Profiles(
            member=MemberProfile(
                care_plan_id=1,
                subdivision_code="US-NY",
                state=State(abbreviation="NY"),
                tel_number="+12125551515",
            )
        ),
    )


@pytest.fixture(scope="function")
def translated_mpractice_member_uk(country: Country) -> TranslatedMPracticeMember:
    return TranslatedMPracticeMember(
        id=3,
        first_name="Bob",
        last_name="Johnson",
        email="bob.johnson@xxx.com",
        created_at=datetime.datetime(2022, 1, 1, 0, 0, 0),
        care_plan_id=1,
        dosespot="{}",
        state_abbreviation="ZZ",
        country_code="UK",
        organization_name="test org",
        organization_education_only=False,
        organization_rx_enabled=True,
        name="Bob Johnson",
        country=country,
        organization=Organization(
            name="test org",
            education_only=False,
            rx_enabled=True,
        ),
        profiles=Profiles(
            member=MemberProfile(
                care_plan_id=1,
                subdivision_code=None,
                state=State(abbreviation="ZZ"),
                tel_number=None,
            )
        ),
    )


@pytest.fixture(scope="function")
def translated_mpractice_member_anonymous(dosespot: dict) -> TranslatedMPracticeMember:
    return TranslatedMPracticeMember(
        id=2,
        first_name=None,
        last_name=None,
        care_plan_id=1,
        dosespot=json.dumps(dosespot),
        phone_number="+12125551515",
        subdivision_code="US-NY",
        state_abbreviation="NY",
        country_code="US",
        organization_name="test org",
        organization_education_only=False,
        organization_rx_enabled=True,
        name=None,
        email=None,
        country=None,
        organization=None,
        profiles=Profiles(
            member=MemberProfile(
                care_plan_id=1,
                subdivision_code="US-NY",
                state=State(abbreviation="NY"),
                tel_number="+12125551515",
            )
        ),
        created_at=None,
    )


@pytest.fixture(scope="function")
def translated_mpractice_practitioner(
    ca_vertical: Vertical,
) -> TranslatedMPracticePractitioner:
    return TranslatedMPracticePractitioner(
        id=1,
        name="Stephanie Schmitt",
        profiles=Profiles(
            practitioner=PractitionerProfile(
                can_prescribe=True,
                messaging_enabled=True,
                certified_subdivision_codes=["US-NY"],
                vertical_objects=[ca_vertical],
            ),
        ),
        certified_states=["NY"],
        dosespot=json.dumps({"clinic_key": "NEYg4R", "clinic_id": 370, "user_id": 482}),
    )


@pytest.fixture(scope="function")
def translated_provider_appointment_100(
    organization: Organization,
    prescription_info_not_enabled: PrescriptionInfo,
    post_session_note: SessionMetaInfo,
    ca_vertical: Vertical,
    translated_mpractice_member: TranslatedMPracticeMember,
    translated_mpractice_practitioner: TranslatedMPracticePractitioner,
    structured_internal_note: StructuredInternalNote,
    provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire,
) -> TranslatedProviderAppointment:
    return TranslatedProviderAppointment(
        id=997948328,
        appointment_id=100,
        scheduled_start=datetime.datetime(2024, 3, 21, 10, 0, 0),
        scheduled_end=datetime.datetime(2024, 3, 21, 10, 15, 0),
        cancelled_at=None,
        cancellation_policy="conservative",
        cancelled_note="cancelled by patient",
        member_started_at=datetime.datetime(2024, 3, 21, 10, 0, 0),
        member_ended_at=datetime.datetime(2024, 3, 21, 10, 14, 0),
        member_disconnected_at=datetime.datetime(2024, 3, 21, 10, 5, 0),
        practitioner_started_at=datetime.datetime(2024, 3, 21, 10, 0, 0),
        practitioner_ended_at=datetime.datetime(2024, 3, 21, 10, 14, 9),
        practitioner_disconnected_at=datetime.datetime(2024, 3, 21, 10, 5, 1),
        phone_call_at=datetime.datetime(2024, 3, 21, 10, 0, 1),
        privacy="basic",
        privilege_type="standard",
        purpose="birth_planning",
        state="PAYMENT_PENDING",
        pre_session=SessionMetaInfo(notes="pre-session notes"),
        post_session=post_session_note,
        need=Need(id=1, name="egg freeze", description="timeline for egg freeze"),
        video=None,
        product=Product(
            practitioner=translated_mpractice_practitioner,
            vertical_id=4,
        ),
        member=translated_mpractice_member,
        prescription_info=prescription_info_not_enabled,
        rx_enabled=False,
        rx_reason="pharmacy_info_not_added",
        rx_written_via="dosespot",
        structured_internal_note=structured_internal_note,
        provider_addenda=provider_addenda_and_questionnaire,
    )


def get_expected_appointment_for_list(
    appointment: Appointment,
    repeat_patient_appointment_count: int | None = None,
    reschedule_history: RescheduleHistory | None = None,
) -> ProviderAppointmentForList:
    user = appointment.member_schedule.user
    previous_scheduled_start = (
        reschedule_history.scheduled_start if reschedule_history else None
    )

    payment_captured_at = (
        appointment.payment.captured_at if appointment.payment else None
    )
    payment_amount = float(appointment.payment.amount) if appointment.payment else None
    total_used_credits = None
    credit_latest_used_at = None
    if appointment.credits:
        total_used_credits = float(
            sum([credit.amount for credit in appointment.credits if credit.used_at])
        )
        credit_latest_used_at = max(
            [credit.used_at for credit in appointment.credits if credit.used_at]
        )
    fees_count = len(appointment.fees) if appointment.fees else None
    return ProviderAppointmentForList(
        id=appointment.id,
        scheduled_start=appointment.scheduled_start,
        scheduled_end=appointment.scheduled_end,
        member_id=user.id,
        practitioner_id=appointment.product.user_id,
        member_first_name=user.first_name,
        member_last_name=user.last_name,
        member_country_code=user.profile.country_code,
        privacy=appointment.privacy,
        privilege_type=appointment.privilege_type,
        cancelled_at=appointment.cancelled_at,
        disputed_at=appointment.disputed_at,
        member_started_at=appointment.member_started_at,
        member_ended_at=appointment.member_ended_at,
        practitioner_started_at=appointment.practitioner_started_at,
        practitioner_ended_at=appointment.practitioner_ended_at,
        json=str(appointment.json),
        repeat_patient_appointment_count=repeat_patient_appointment_count,
        rescheduled_from_previous_appointment_time=previous_scheduled_start,
        payment_captured_at=payment_captured_at,
        payment_amount=payment_amount,
        total_used_credits=total_used_credits,
        credit_latest_used_at=credit_latest_used_at,
        fees_count=fees_count,
    )


"""
Questionnaire related data
"""


@pytest.fixture(scope="function")
def answer(question: MPracticeQuestion) -> MPracticeAnswer:
    return MPracticeAnswer(
        id=1,
        sort_order=1,
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
        question_id=question.id,
        text="test text",
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def translated_answer() -> TranslatedMPracticeAnswer:
    return TranslatedMPracticeAnswer(
        id=1,
        sort_order=1,
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
        question_id=1,
        text="test text",
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def question() -> MPracticeQuestion:
    return MPracticeQuestion(
        id=1,
        sort_order=1,
        label="label",
        type=QuestionTypes.CONDITION.value,
        required=False,
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
        question_set_id=1,
        non_db_answer_options_json=None,
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def translated_question(
    translated_answer: TranslatedMPracticeAnswer,
) -> TranslatedMPracticeQuestion:
    return TranslatedMPracticeQuestion(
        id=1,
        sort_order=1,
        label="label",
        type=QuestionTypes.CONDITION.value,
        required=False,
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
        question_set_id=1,
        non_db_answer_options_json=None,
        soft_deleted_at=None,
        answers=[translated_answer],
    )


@pytest.fixture(scope="function")
def question_set() -> MPracticeQuestionSet:
    return MPracticeQuestionSet(
        id=1,
        sort_order=1,
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
        prerequisite_answer_id=None,
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def translated_question_set(
    translated_question: TranslatedMPracticeQuestion,
) -> TranslatedMPracticeQuestionSet:
    return TranslatedMPracticeQuestionSet(
        id=1,
        sort_order=1,
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
        prerequisite_answer_id=None,
        soft_deleted_at=None,
        questions=[translated_question],
    )


@pytest.fixture(scope="function")
def questionnaire() -> MPracticeQuestionnaire:
    return MPracticeQuestionnaire(
        id=1,
        sort_order=1,
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
        description_text="description",
        title_text="title",
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def trigger_answer_ids() -> List[int]:
    return [1]


@pytest.fixture(scope="function")
def translated_questionnaire(
    translated_question_set: TranslatedMPracticeQuestionSet,
    trigger_answer_ids: List[int],
) -> TranslatedMPracticeQuestionnaire:
    return TranslatedMPracticeQuestionnaire(
        id=1,
        sort_order=1,
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
        description_text="description",
        title_text="title",
        soft_deleted_at=None,
        question_sets=[translated_question_set],
        trigger_answer_ids=trigger_answer_ids,
    )


@pytest.fixture(scope="function")
def recorded_answer() -> MPracticeRecordedAnswer:
    return MPracticeRecordedAnswer(
        question_id=1,
        user_id=1,
        appointment_id=1,
        question_type_in_enum=QuestionTypes.CONDITION,
        answer_id=1,
        text="test_text",
        date=datetime.date(2024, 3, 22),
        payload_string=None,
    )


@pytest.fixture(scope="function")
def recorded_answer_without_appointment_id() -> MPracticeRecordedAnswer:
    return MPracticeRecordedAnswer(
        question_id=1,
        user_id=1,
        appointment_id=None,
        question_type_in_enum=QuestionTypes.CONDITION,
        answer_id=1,
        text="test_text",
        date=datetime.date(2024, 3, 22),
        payload_string=None,
    )


@pytest.fixture(scope="function")
def translated_recorded_answer() -> TranslatedMPracticeRecordedAnswer:
    return TranslatedMPracticeRecordedAnswer(
        question_id=1,
        user_id=1,
        appointment_id=997948365,
        question_type_in_enum=QuestionTypes.CONDITION,
        question_type=QuestionTypes.CONDITION.name,
        answer_id=1,
        text="test_text",
        date=datetime.date(2024, 3, 22),
        payload={"text": "test_text"},
    )


@pytest.fixture(scope="function")
def recorded_answer_set() -> MPracticeRecordedAnswerSet:
    return MPracticeRecordedAnswerSet(
        id=1,
        source_user_id=1,
        appointment_id=1,
        questionnaire_id=1,
        draft=False,
        modified_at=datetime.datetime(2024, 2, 1, 0, 0, 0),
        submitted_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
    )


@pytest.fixture(scope="function")
def translated_recorded_answer_set(
    translated_recorded_answer,
) -> TranslatedMPracticeRecordedAnswerSet:
    return TranslatedMPracticeRecordedAnswerSet(
        id=1,
        source_user_id=1,
        appointment_id=997948365,
        questionnaire_id=1,
        draft=False,
        modified_at=datetime.datetime(2024, 2, 1, 0, 0, 0),
        submitted_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
        recorded_answers=[translated_recorded_answer],
    )


@pytest.fixture(scope="function")
def provider_addendum_answer() -> MPracticeProviderAddendumAnswer:
    return MPracticeProviderAddendumAnswer(
        question_id=1,
        addendum_id=1,
        answer_id=1,
        text="test text",
        date=datetime.date(2024, 1, 1),
    )


@pytest.fixture(scope="function")
def provider_addendum(
    questionnaire: MPracticeQuestionnaire,
) -> MPracticeProviderAddendum:
    return MPracticeProviderAddendum(
        id=1,
        questionnaire_id=questionnaire.id,
        user_id=1,
        appointment_id=1,
        submitted_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
        associated_answer_id=None,
    )


@pytest.fixture(scope="function")
def translated_provider_addendum(
    provider_addendum_answer,
) -> TranslatedMPracticeProviderAddendum:
    return TranslatedMPracticeProviderAddendum(
        id=1,
        questionnaire_id=1,
        user_id=1,
        appointment_id=997948365,
        submitted_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
        associated_answer_id=None,
        provider_addendum_answers=[provider_addendum_answer],
    )


@pytest.fixture(scope="function")
def structured_internal_note(
    translated_questionnaire: TranslatedMPracticeQuestionnaire,
    translated_question_set: TranslatedMPracticeQuestionSet,
    translated_recorded_answer_set: TranslatedMPracticeRecordedAnswerSet,
    translated_recorded_answer: TranslatedMPracticeRecordedAnswer,
) -> StructuredInternalNote:
    return StructuredInternalNote(
        questionnaire=translated_questionnaire,
        question_sets=[translated_question_set],
        recorded_answer_set=translated_recorded_answer_set,
        recorded_answers=[translated_recorded_answer],
    )


@pytest.fixture(scope="function")
def provider_addenda_and_questionnaire(
    translated_questionnaire: TranslatedMPracticeQuestionnaire,
    translated_provider_addendum: TranslatedMPracticeProviderAddendum,
):
    return MPracticeProviderAddendaAndQuestionnaire(
        questionnaire=translated_questionnaire,
        provider_addenda=[translated_provider_addendum],
    )
