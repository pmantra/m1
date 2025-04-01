from __future__ import annotations

import datetime
import json
from typing import List
from unittest import mock
from unittest.mock import MagicMock

import pytest

from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.reschedule_history import RescheduleHistory
from appointments.pytests.factories import PaymentAccountingEntryFactory
from clinical_documentation.models.mpractice_template import MPracticeTemplate
from clinical_documentation.models.note import (
    AnswerV2,
    ProviderAddendumAnswerV2,
    ProviderAddendumV2,
    QuestionnaireV2,
    QuestionSetV2,
    QuestionV2,
    RecordedAnswerSetV2,
    RecordedAnswerV2,
)
from clinical_documentation.models.translated_note import (
    MPracticeProviderAddendaAndQuestionnaire,
    StructuredInternalNote,
    TranslatedAnswerV2,
    TranslatedProviderAddendumV2,
    TranslatedQuestionnaireV2,
    TranslatedQuestionSetV2,
    TranslatedQuestionV2,
    TranslatedRecordedAnswerSetV2,
    TranslatedRecordedAnswerV2,
)
from clinical_documentation.repository.mpractice_questionnaire import (
    MPracticeQuestionnaireRepository,
)
from clinical_documentation.repository.mpractice_template import (
    MPracticeTemplateRepository,
)
from clinical_documentation.repository.post_appointment_note import (
    PostAppointmentNoteRepository,
)
from clinical_documentation.services.note import ClinicalDocumentationNoteService
from geography import Country
from models.questionnaires import PROVIDER_ADDENDA_QUESTIONNAIRE_OID, QuestionTypes
from models.tracks import TrackName
from mpractice.models.appointment import (
    MPracticeMember,
    MPracticePractitioner,
    ProviderAppointment,
    ProviderAppointmentForList,
    Vertical,
)
from mpractice.models.translated_appointment import (
    MemberProfile,
    Organization,
    Profiles,
    SessionMetaInfo,
    State,
    TranslatedMPracticeMember,
)
from mpractice.repository.provider_appointment import ProviderAppointmentRepository
from mpractice.repository.provider_appointment_for_list import (
    ProviderAppointmentForListRepository,
)
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
    MPracticeTemplateFactory,
    OrganizationFactory,
    PractitionerUserFactory,
    StateFactory,
)


@pytest.fixture(scope="function")
def post_appointment_note_repo(session) -> PostAppointmentNoteRepository:
    return PostAppointmentNoteRepository(session=session)


@pytest.fixture(scope="function")
def app_metadata() -> [AppointmentMetaData]:
    appt1 = AppointmentFactory.create(
        id=100,
        scheduled_start=datetime.datetime(2023, 1, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 1, 1, 11, 00, 00),
    )

    appt2 = AppointmentFactory.create(
        id=200,
        scheduled_start=datetime.datetime(2023, 1, 1, 10, 00, 00),
        scheduled_end=datetime.datetime(2023, 1, 1, 11, 00, 00),
    )

    notes = [
        AppointmentMetaDataFactory.create(
            id=101,
            appointment_id=appt1.id,
            content="metadata content 101",
            draft=False,
            created_at=datetime.datetime(2023, 1, 1, 10, 00, 00),
            modified_at=datetime.datetime(2023, 1, 1, 11, 00, 00),
        ),
        AppointmentMetaDataFactory.create(
            id=102,
            appointment_id=appt1.id,
            content="metadata content 102",
            draft=True,
            created_at=datetime.datetime(2023, 1, 1, 10, 00, 00),
            modified_at=datetime.datetime(2023, 1, 1, 12, 00, 00),
        ),
        AppointmentMetaDataFactory.create(
            id=203,
            appointment_id=appt2.id,
            content="metadata content 102",
            draft=True,
            created_at=datetime.datetime(2023, 1, 1, 10, 00, 00),
            modified_at=datetime.datetime(2023, 1, 1, 12, 00, 00),
        ),
    ]

    return notes


@pytest.fixture(scope="function")
def provider_appointment_repo(session) -> ProviderAppointmentRepository:
    return ProviderAppointmentRepository(session=session)


@pytest.fixture(scope="function")
def provider_appointment_for_list_repo(session) -> ProviderAppointmentForListRepository:
    return ProviderAppointmentForListRepository(session=session)


@pytest.fixture(scope="function")
def questionnaire_repo(session) -> MPracticeQuestionnaireRepository:
    return MPracticeQuestionnaireRepository(session=session)


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
        content="metadata content 101",
        draft=True,
        created_at=datetime.datetime(2023, 1, 1, 10, 0, 0),
        modified_at=datetime.datetime(2023, 1, 1, 12, 0, 0),
    )
    AppointmentMetaDataFactory.create(
        id=102,
        appointment_id=appt.id,
        content="metadata content 102",
        draft=True,
        created_at=datetime.datetime(2023, 2, 1, 10, 0, 0),
        modified_at=datetime.datetime(2023, 2, 2, 12, 0, 0),
    )
    # latest post session note
    AppointmentMetaDataFactory.create(
        id=103,
        appointment_id=appt.id,
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
        content="metadata content 301",
        draft=True,
        created_at=datetime.datetime(2023, 3, 2, 10, 00, 00),
        modified_at=datetime.datetime(2023, 3, 3, 10, 00, 00),
    )
    AppointmentMetaDataFactory.create(
        appointment_id=appt.id,
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
def mock_mpractice_questionnaire_repo() -> MagicMock:
    with mock.patch(
        "clinical_documentation.repository.mpractice_questionnaire.MPracticeQuestionnaireRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture(scope="function")
def note_service(
    mock_mpractice_questionnaire_repo,
) -> ClinicalDocumentationNoteService:
    return ClinicalDocumentationNoteService(
        questionnaire_repo=mock_mpractice_questionnaire_repo
    )


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
        id=997948328,
        scheduled_start=datetime.datetime(2024, 3, 21, 10, 0, 0),
        scheduled_end=datetime.datetime(2024, 3, 21, 10, 15, 0),
        member_started_at=datetime.datetime(2024, 3, 21, 10, 0, 0),
        practitioner_started_at=datetime.datetime(2024, 3, 21, 10, 0, 0),
        practitioner_id=2,
        member_id=3,
        vertical_id=4,
        privacy="basic",
        privilege_type="standard",
        client_notes="pre-session notes",
        need_name="egg freeze",
        need_description="timeline for egg freeze",
        video='{"member_token": "mt", "practitioner_token": "pt", "session_id": "123"}',
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
def vertical() -> Vertical:
    return Vertical(id=1, filter_by_state=True, can_prescribe=True)


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
        dosespot="{}",
        country_code="US",
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
        first_name="Alice",
        last_name="Johnson",
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
def answer(question: QuestionV2) -> AnswerV2:
    return AnswerV2(
        id=1,
        sort_order=1,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        question_id=question.id,
        text="test text",
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def translated_answer() -> TranslatedAnswerV2:
    return TranslatedAnswerV2(
        id=1,
        sort_order=1,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        question_id=1,
        text="test text",
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def question() -> QuestionV2:
    return QuestionV2(
        id=1,
        sort_order=1,
        label="label",
        type=QuestionTypes.CONDITION.value,
        required=False,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        question_set_id=1,
        non_db_answer_options_json=None,
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def translated_question(
    translated_answer: TranslatedAnswerV2,
) -> TranslatedQuestionV2:
    return TranslatedQuestionV2(
        id=1,
        sort_order=1,
        label="label",
        type=QuestionTypes.CONDITION.value,
        required=False,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        question_set_id=1,
        non_db_answer_options_json=None,
        soft_deleted_at=None,
        answers=[translated_answer],
    )


@pytest.fixture(scope="function")
def question_set() -> QuestionSetV2:
    return QuestionSetV2(
        id=1,
        sort_order=1,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        prerequisite_answer_id=None,
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def translated_question_set(
    translated_question: TranslatedQuestionV2,
) -> TranslatedQuestionSetV2:
    return TranslatedQuestionSetV2(
        id=1,
        sort_order=1,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        prerequisite_answer_id=None,
        soft_deleted_at=None,
        questions=[translated_question],
    )


@pytest.fixture(scope="function")
def questionnaire() -> QuestionnaireV2:
    return QuestionnaireV2(
        id=1,
        sort_order=1,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        description_text="description",
        title_text="title",
        soft_deleted_at=None,
    )


@pytest.fixture(scope="function")
def trigger_answer_ids() -> List[int]:
    return [1]


@pytest.fixture(scope="function")
def translated_questionnaire(
    translated_question_set: TranslatedQuestionSetV2,
    trigger_answer_ids: List[int],
) -> TranslatedQuestionnaireV2:
    return TranslatedQuestionnaireV2(
        id=1,
        sort_order=1,
        oid=PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
        description_text="description",
        title_text="title",
        soft_deleted_at=None,
        question_sets=[translated_question_set],
        trigger_answer_ids=trigger_answer_ids,
    )


@pytest.fixture(scope="function")
def provider_addendum_answer() -> ProviderAddendumAnswerV2:
    return ProviderAddendumAnswerV2(
        question_id=1,
        addendum_id=1,
        answer_id=1,
        text="test text",
        date=datetime.date(2024, 1, 1),
    )


@pytest.fixture(scope="function")
def provider_addendum(
    questionnaire: QuestionnaireV2,
) -> ProviderAddendumV2:
    return ProviderAddendumV2(
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
) -> TranslatedProviderAddendumV2:
    return TranslatedProviderAddendumV2(
        id=1,
        questionnaire_id=1,
        user_id=1,
        appointment_id=997948365,
        submitted_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
        associated_answer_id=None,
        provider_addendum_answers=[provider_addendum_answer],
    )


@pytest.fixture(scope="function")
def provider_addenda_and_questionnaire(
    translated_questionnaire: TranslatedQuestionnaireV2,
    translated_provider_addendum: TranslatedProviderAddendumV2,
):
    return MPracticeProviderAddendaAndQuestionnaire(
        questionnaire=translated_questionnaire,
        provider_addenda=[translated_provider_addendum],
    )


@pytest.fixture(scope="function")
def mock_note_service_for_provider_addenda_resource() -> MagicMock:
    with mock.patch(
        "clinical_documentation.services.note.ClinicalDocumentationNoteService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "clinical_documentation.resource.provider_addenda.ClinicalDocumentationNoteService",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def recorded_answer_set() -> RecordedAnswerSetV2:
    return RecordedAnswerSetV2(
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
) -> TranslatedRecordedAnswerSetV2:
    return TranslatedRecordedAnswerSetV2(
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
def recorded_answer() -> RecordedAnswerV2:
    return RecordedAnswerV2(
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
def translated_recorded_answer() -> TranslatedRecordedAnswerV2:
    return TranslatedRecordedAnswerV2(
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
def recorded_answer_without_appointment_id() -> RecordedAnswerV2:
    return RecordedAnswerV2(
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
def structured_internal_note(
    translated_questionnaire: TranslatedQuestionnaireV2,
    translated_question_set: TranslatedQuestionSetV2,
    translated_recorded_answer_set: TranslatedRecordedAnswerSetV2,
    translated_recorded_answer: TranslatedRecordedAnswerV2,
) -> StructuredInternalNote:
    return StructuredInternalNote(
        questionnaire=translated_questionnaire,
        question_sets=[translated_question_set],
        recorded_answer_set=translated_recorded_answer_set,
        recorded_answers=[translated_recorded_answer],
    )


@pytest.fixture(scope="function")
def mock_note_service_for_structured_internal_notes_resource() -> MagicMock:
    with mock.patch(
        "clinical_documentation.services.note.ClinicalDocumentationNoteService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "clinical_documentation.resource.structured_internal_notes.ClinicalDocumentationNoteService",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def mpractice_template_repository(session) -> MPracticeTemplateRepository:
    return MPracticeTemplateRepository(session=session)


@pytest.fixture(scope="function")
def created_mpractice_template(mpractice_template_repository) -> MPracticeTemplate:
    template = MPracticeTemplateFactory.build()
    created = mpractice_template_repository.create(instance=template)
    return created


@pytest.fixture(scope="function")
def mock_mpractice_template_service_for_singleton_resource() -> MagicMock:
    with mock.patch(
        "clinical_documentation.services.mpractice_template.MPracticeTemplateService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "clinical_documentation.resource.mpractice_template.MPracticeTemplateService",
            autospec=True,
            return_value=m,
        ):
            yield m


@pytest.fixture(scope="function")
def mock_mpractice_template_service_for_multiple_resource() -> MagicMock:
    with mock.patch(
        "clinical_documentation.services.mpractice_template.MPracticeTemplateService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "clinical_documentation.resource.mpractice_templates.MPracticeTemplateService",
            autospec=True,
            return_value=m,
        ):
            yield m
