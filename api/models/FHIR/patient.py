from __future__ import annotations

from typing import Union

from dateutil.parser import parse

from authn.models.user import User
from health.services.health_profile_service import HealthProfileService
from models.questionnaires import (
    DOB_QUESTION_OID,
    GENDER_FREETEXT_QUESTION_OID,
    GENDER_MULTISELECT_QUESTION_OID,
    GENDER_OTHER_ANSWER_OID,
    HEIGHT_QUESTION_OID,
    WEIGHT_QUESTION_OID,
)
from utils.age import calculate_age
from utils.data import calculate_bmi
from utils.log import logger
from views.schemas.FHIR.common import (
    FHIR_DATETIME_FORMAT,
    fhir_identifier_from_model,
    get_system_name,
)
from views.schemas.FHIR.patient import FHIRPatientSchema

log = logger(__name__)

# nonsense made-up urls--we're waiting for trefolia-on-fhir for real ones
ADDRESS_COUNTRY_EXTENSION_URL = (
    "https://mavenclinic.com/fhir/StructureDefinition/address-country"
)
CHILD_EXTENSION_URL = "https://mavenclinic.com/fhir/StructureDefinition/child"
ACTIVITY_LEVEL_EXTENSION_URL = (
    "https://mavenclinic.com/fhir/StructureDefinition/activity-level"
)
WEIGHT_EXTENSION_URL = "https://mavenclinic.com/fhir/StructureDefinition/weight"
HEIGHT_EXTENSION_URL = "https://mavenclinic.com/fhir/StructureDefinition/height"
CURRENT_PROGRAM_EXTENSION_URL = (
    "https://mavenclinic.com/fhir/StructureDefinition/current-program"
)
TRACKS_EXTENSION_URL = "https://mavenclinic.com/fhir/StructureDefinition/tracks"
INACTIVE_TRACKS_EXTENSION_URL = (
    "https://mavenclinic.com/fhir/StructureDefinition/inactive-tracks"
)
AGE_EXTENSION_URL = "https://mavenclinic.com/fhir/StructureDefinition/age"

# https://www.hl7.org/fhir/iso3166.html
ISO_3166_SYSTEM = "urn:iso:std:iso:3166"


class FHIRPatientSchemaData:
    @classmethod
    def generate_for_user(cls, user, version=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return FHIRPatientSchema().dump(
            {
                "identifier": cls._get_identifiers(user),
                "name": cls._get_names(user),
                "telecom": cls._get_contact_points(user),
                "gender": cls._get_gender(user),
                "sexAtBirth": cls._get_sex_at_birth(user),
                "address": cls._get_addresses(user),
                "birthDate": cls._get_birthdate(user),
                "extension": cls._get_extensions(user, version),
                "active": user.active,
                "fertilityTreatmentStatus": cls._get_fertility_treatment_status(user),
                # we don't have this info yet
                "communication": [],
                # A temporary place to host pregnancy due date.
                # In the future, due date along with other pregnancy data will be moved to health profile platform.
                "pregnancyDueDate": cls.get_pregnancy_due_date(user),
            }
        )

    @classmethod
    def generate_for_user_from_questionnaire_answers(cls, answer_set, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return FHIRPatientSchema().dump(
            {
                "identifier": cls._get_identifiers(user),
                "name": cls._get_names(user),
                "telecom": cls._get_contact_points(user),
                "gender": cls._get_gender_from_questionnaire_answers(answer_set),
                "address": cls._get_addresses(user),
                "birthDate": cls._get_birthdate_from_questionnaire_answers(answer_set),
                "extension": cls._get_extensions_from_questionnaire_answers(
                    user=user, answer_set=answer_set
                ),
                # we don't have this info
                "active": None,
                # we don't have this info yet
                "communication": [],
            }
        )

    @classmethod
    def _get_identifiers(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [fhir_identifier_from_model(user)]

    @classmethod
    def _get_names(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        given_name_array = [user.first_name]
        if user.middle_name:
            given_name_array.append(user.middle_name)

        return [{"family": user.last_name, "given": given_name_array}]

    @classmethod
    def _get_contact_points(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        contact_points = [{"system": "email", "value": user.email, "use": None}]
        if user.member_profile.phone_number:
            contact_points.append(
                {
                    "system": "phone",
                    "value": user.member_profile.phone_number,
                    "use": None,
                }
            )
        return contact_points

    @classmethod
    def _get_gender(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return user.health_profile.json.get("gender")

    @classmethod
    def _get_sex_at_birth(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return user.health_profile.json.get("sex_at_birth")

    @classmethod
    def _get_gender_from_questionnaire_answers(cls, answer_set):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        selected_gender_answers = [
            ra.answer
            for ra in answer_set.recorded_answers
            if ra.question.oid == GENDER_MULTISELECT_QUESTION_OID
        ]
        freetext_gender = next(
            # New iOS health binder uses payload attr instead of text.
            # Be sure other clients do too when they implement.
            (
                (ra.payload and ra.payload.get("text")) or ""
                for ra in answer_set.recorded_answers
                if ra.question.oid == GENDER_FREETEXT_QUESTION_OID
            ),
            "",
        )
        if freetext_gender:
            selected_genders = [
                answer.text
                for answer in selected_gender_answers
                if answer.oid != GENDER_OTHER_ANSWER_OID
            ]
        else:
            selected_genders = [answer.text for answer in selected_gender_answers]
        joined_gender_strings = ",".join(selected_genders) + freetext_gender
        if joined_gender_strings:
            return joined_gender_strings

    @classmethod
    def _get_addresses(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if user.member_profile.address:
            if user.member_profile.address.country:
                country_extension = cls._country_extension(
                    user.member_profile.address.country
                )
            else:
                country_extension = []
            return [
                {
                    # There can be multiple lines, but it doesn't look like that's supported in our db
                    # so let's just put the one line in an array
                    "line": [user.member_profile.address.street_address],
                    "city": user.member_profile.address.city,
                    "state": user.member_profile.address.state,
                    "postalCode": user.member_profile.address.zip_code,
                    "use": None,
                    "period": None,
                    "extension": country_extension,
                }
            ]
        else:
            return []

    @classmethod
    def _get_birthdate(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return user.health_profile.date_of_birth or user.health_profile.birthday

    @classmethod
    def _get_birthdate_from_questionnaire_answers(cls, answer_set):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return next(
            (
                ra.payload and ra.payload.get("text")
                for ra in answer_set.recorded_answers
                if ra.question.oid == DOB_QUESTION_OID
            ),
            None,
        )

    @classmethod
    def _country_extension(cls, country_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [
            {
                "url": ADDRESS_COUNTRY_EXTENSION_URL,
                "extension": [
                    {
                        "url": "codeable_concept",
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": ISO_3166_SYSTEM,
                                    "version": None,
                                    # This is an ISO3166 2-letter code!
                                    "display": country_code,
                                    "code": country_code,
                                    "userSelected": True,
                                }
                            ]
                        },
                    },
                    {
                        "url": "flagged",
                        # This flag is for being unable to prescribe to non-US members
                        # AFAIK right now (9/9/20) prescriptions are unavailable for
                        # non-US members
                        "valueBoolean": country_code != "US",
                    },
                    cls._label_extension_field("country"),
                ],
            }
        ]

    @classmethod
    def _get_extensions(cls, user, version=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        extensions = []
        children = user.health_profile.children
        activity_level = user.health_profile.json.get("activity_level")
        weight = user.health_profile.weight
        height = user.health_profile.height
        bmi = user.health_profile.bmi
        age = user.health_profile.age

        for child in children:
            extensions.append(cls._child_extension(child))
        if activity_level:
            extensions.append(cls._activity_level_extension(activity_level))
        if weight:
            extensions.append(cls._weight_extension(weight, bmi))
        if height:
            extensions.append(cls._height_extension(height))
        if user.is_enterprise:
            extensions.append(cls._current_program_extension(user))
            extensions.append(cls._tracks_extension(user, version))
            extensions.append(cls._inactive_tracks_extension(user, version))
        if cls._get_birthdate(user):
            extensions.append(cls._age_extension(age))
        return extensions

    @classmethod
    def _get_extensions_from_questionnaire_answers(cls, user, answer_set):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        extensions = []
        weight = next(
            (
                # There shouldn't be any float input, but just in case
                # TODO: add some error checking
                ra.payload and ra.payload.get("text") and int(float(ra.payload["text"]))
                for ra in answer_set.recorded_answers
                if ra.question.oid == WEIGHT_QUESTION_OID
            ),
            None,
        )
        height = next(
            (
                ra.payload and ra.payload.get("text") and int(float(ra.payload["text"]))
                for ra in answer_set.recorded_answers
                if ra.question.oid == HEIGHT_QUESTION_OID
            ),
            None,
        )
        bmi = calculate_bmi(height=height, weight=weight) if height and weight else 0

        dob = cls._get_birthdate_from_questionnaire_answers(answer_set)
        if weight:
            extensions.append(cls._weight_extension(weight, bmi))
        if height:
            extensions.append(cls._height_extension(height))
        if user.is_enterprise:
            extensions.append(cls._current_program_extension(user))
            extensions.append(cls._tracks_extension(user))
            extensions.append(cls._inactive_tracks_extension(user))
        if dob:
            try:
                dob_datetime = parse(dob)
                age = calculate_age(dob_datetime)

                if age <= 0:
                    log.warn(
                        "Invalid date of birth in health binder answer",
                        dob=dob,
                        user_id=user.id,
                    )
                else:
                    extensions.append(cls._age_extension(age))
            except Exception as e:
                log.warn(
                    "Cannot parse date of birth in health binder answer",
                    error=e,
                    dob=dob,
                    user_id=user.id,
                )
        return extensions

    @classmethod
    def _child_extension(cls, child_dict):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {
            "url": CHILD_EXTENSION_URL,
            "extension": [
                {"url": "name", "valueString": child_dict.get("name")},
                {"url": "date_of_birth", "valueDate": child_dict.get("birthday")},
                cls._label_extension_field("child"),
            ],
        }

    @classmethod
    def _activity_level_extension(cls, activity_level):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {
            "url": ACTIVITY_LEVEL_EXTENSION_URL,
            "extension": [
                {
                    "url": "codeable_concept",
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": get_system_name(),
                                "version": None,
                                "display": activity_level,
                                "code": activity_level,
                                "userSelected": True,
                            }
                        ]
                    },
                },
                cls._label_extension_field("activity_level"),
            ],
        }

    @classmethod
    def _weight_extension(cls, weight, bmi):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        flagged = False
        if bmi and bmi >= 30:
            flagged = True
        return {
            "url": WEIGHT_EXTENSION_URL,
            "extension": [
                {"url": "weight", "valueInteger": weight},
                {"url": "flagged", "valueBoolean": flagged},
                cls._label_extension_field("weight"),
            ],
        }

    @classmethod
    def _height_extension(cls, height):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return {
            "url": HEIGHT_EXTENSION_URL,
            "extension": [
                {"url": "height", "valueInteger": height},
                cls._label_extension_field("height"),
            ],
        }

    # This will be removed once the FE is ready to move entirely to _tracks_extension()
    @classmethod
    def _current_program_extension(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        track = user.current_member_track
        return {
            "url": CURRENT_PROGRAM_EXTENSION_URL,
            "extension": [
                {"url": "currentTrack", "valueString": track.display_name},
                {
                    "url": "currentPhase",
                    "valueString": track.current_phase.display_name,
                },
                cls._label_extension_field("program"),
            ],
        }

    @classmethod
    def _tracks_extension(cls, user, version=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return cls._get_tracks_extension(
            TRACKS_EXTENSION_URL, version, user.active_tracks
        )

    @classmethod
    def _inactive_tracks_extension(cls, user, version=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return cls._get_tracks_extension(
            INACTIVE_TRACKS_EXTENSION_URL, version, user.inactive_tracks
        )

    @classmethod
    def _get_tracks_extension(cls, tracks_url: str, version: int, tracks: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        def get_track_period(track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            start = None
            end = None

            if track.current_phase:
                if track.current_phase.started_at:
                    start = track.current_phase.started_at.strftime(
                        FHIR_DATETIME_FORMAT
                    )
                if track.current_phase.ended_at:
                    end = track.current_phase.ended_at.strftime(FHIR_DATETIME_FORMAT)

            return {"start": start, "end": end}

        def get_track_phase_name(track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            phase_name = None
            if track.current_phase:
                phase_name = track.current_phase.display_name

            return phase_name

        if version == 2:
            return {
                # V2 Response Format
                "url": tracks_url,
                "extension": [
                    {
                        "url": track.id,
                        "extension": [
                            {"url": "name", "valueString": track.name},
                            {"url": "displayName", "valueString": track.display_name},
                            {"url": "period", "valuePeriod": get_track_period(track)},
                            {
                                "url": "currentPhase",
                                "valueString": get_track_phase_name(track),
                            },
                        ],
                    }
                    for track in tracks
                ],
            }
        else:
            return {
                # V1 / Default Response Format
                "url": tracks_url,
                "extension": [
                    {
                        "url": track.id,
                        "extension": [
                            {"url": "name", "valueString": track.display_name},
                            {"url": "period", "valuePeriod": get_track_period(track)},
                            {
                                "url": "currentPhase",
                                "valueString": get_track_phase_name(track),
                            },
                        ],
                    }
                    for track in tracks
                ],
            }

    @classmethod
    def _age_extension(cls, age: int) -> dict:
        if age:
            flagged = age >= 35
        else:
            flagged = False
        return {
            "url": AGE_EXTENSION_URL,
            "extension": [
                {"url": "age", "valueInteger": age},
                {"url": "flagged", "valueBoolean": flagged},
                cls._label_extension_field("age"),
            ],
        }

    @classmethod
    def _label_extension_field(cls, string: str) -> dict:
        return {"url": "label", "valueString": string}

    @classmethod
    def _get_fertility_treatment_status(cls, user: User) -> Union[str, None]:
        return HealthProfileService(user).get_fertility_treatment_status()

    @classmethod
    def get_pregnancy_due_date(cls, user: User) -> str | None:
        return user.health_profile.due_date
