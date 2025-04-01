import datetime
from dataclasses import asdict, dataclass
from typing import List

from flask_babel import format_date, gettext
from marshmallow import ValidationError, fields

from appointments.models.constants import AppointmentTypes
from appointments.utils.provider import get_provider_country_flag
from authn.models.user import User
from l10n.db_strings.translate import TranslateDBFields
from models.profiles import Language
from models.tracks.client_track import TrackModifiers
from providers.service.provider import ProviderService
from views.schemas.common_v3 import (
    CSVIntegerField,
    CSVStringField,
    PaginableArgsSchemaV3,
)


def validate_practitioner_order(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value == "next_availability":
        return value
    else:
        raise ValidationError("Invalid practitioner order_by!")


class MessageableProviderSearchSchema(PaginableArgsSchemaV3):
    user_ids = CSVIntegerField(required=False)
    vertical_ids = CSVIntegerField(required=False)
    specialty_ids = CSVIntegerField(required=False)
    need_ids = CSVIntegerField(required=False)
    language_ids = CSVIntegerField(required=False)


class ProviderSearchSchema(PaginableArgsSchemaV3):
    user_ids = CSVIntegerField(required=False)
    verticals = CSVStringField(required=False)
    vertical_ids = CSVIntegerField(required=False)
    specialties = CSVStringField(required=False)
    specialty_ids = CSVIntegerField(required=False)
    need_ids = CSVIntegerField(required=False)
    need_slugs = CSVStringField(required=False)
    language_ids = CSVIntegerField(required=False)
    can_prescribe = fields.Boolean(required=False)
    product_minutes = fields.Integer(required=False)
    only_free = fields.Boolean(required=False)
    available_in_next_hours = fields.Integer(required=False)
    availability_scope_in_days = fields.Integer(required=False)
    bypass_availability = fields.Boolean(required=False)
    in_state_match = fields.Boolean(required=False)

    order_by = fields.String(
        validate=validate_practitioner_order,
        default="next_availability",
        missing="next_availability",
        required=False,
    )
    type = fields.String(required=False)


# These fields are meant to be a subset of ProviderSearchSchema
class ProvidersLanguagesGetSchema(PaginableArgsSchemaV3):
    vertical_ids = CSVIntegerField(required=False)
    specialty_ids = CSVIntegerField(required=False)
    need_ids = CSVIntegerField(required=False)
    availability_scope_in_days = fields.Integer(required=False)

    order_by = fields.String(
        validate=validate_practitioner_order,
        default="next_availability",
        required=False,
    )


# Copied from the serialize implementation in views/schema/common.py::MavenDateTime
def serialize_datetime(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if isinstance(value, datetime.datetime):
        value = value.replace(tzinfo=None, microsecond=0)
        return value.isoformat()
    elif isinstance(value, datetime.date):
        return value.isoformat()
    else:
        # cached values are already processed
        return value


@dataclass
class ProviderSearchResultStruct:
    __slots__ = (
        "full_name",
        "name",
        "id",
        "image_url",
        "vertical",
        "can_prescribe",
        "next_availability",
        "dynamic_subtext",
        "is_care_advocate",
        "certified_states",
        "country_flag",
        "is_vertical_state_filtered",
        "appointment_type",
    )
    # need to join in Provider and Vertical and certified_states
    full_name: str  # deprecated
    name: str
    id: int  # User id, not Provider
    image_url: str
    vertical: str
    can_prescribe: bool  # use provider_can_prescribe_in_state
    next_availability: str  # iso format
    dynamic_subtext: str
    is_care_advocate: bool
    certified_states: List[str]
    country_flag: str
    is_vertical_state_filtered: bool
    appointment_type: str


@dataclass
class ProviderProfileStruct(ProviderSearchResultStruct):
    __slots__ = (
        "certifications",
        "messaging_enabled",
        "years_experience",
        "education",
        "work_experience",
        "country",
        "cancellation_policy",
        "vertical_long_description",
        "specialties",
        "languages",
        "active",
        "can_request_availability",
        "can_member_interact",
    )
    certifications: List[str]
    messaging_enabled: bool
    years_experience: int
    education: List[str]
    work_experience: List[str]
    country: str
    cancellation_policy: str
    vertical_long_description: str
    specialties: List[str]
    languages: List[str]
    active: bool
    can_request_availability: bool
    can_member_interact: bool


def format_languages(languages: List[str]) -> str:
    """If the provider speaks multiple languages, the text shows a list of languages the provider speaks, with English
    listed last (if applicable) “Speaks [insert other language(s)] & English”.
    """

    # Sort to move 'English' to the end if it exists
    languages.sort(key=lambda x: x == "English")

    # If there's more than one language, join all but the last with ', ', and the last two with ' & '
    if len(languages) > 1:
        return ", ".join(languages[:-1]) + " & " + languages[-1]
    else:
        return languages[0]


def make_dynamic_subtext(
    provider_user: User,
    latest_appointment_date_by_provider_id: dict,
    l10n_flag: bool = False,
) -> str:
    """Return the latest appointment date if we have one, otherwise
    return the list of languages the provider speaks, otherwise
    return nothing.
    """
    if l10n_flag:
        languages = [
            TranslateDBFields().get_translated_language(l.slug, "name", l.name)
            for l in provider_user.practitioner_profile.languages
        ]
    else:
        languages = [l.name for l in provider_user.practitioner_profile.languages]

    last_date = latest_appointment_date_by_provider_id.get(provider_user.id)
    english_only_language = len(languages) == 1 and languages[0] == Language.ENGLISH
    if last_date:
        if l10n_flag:
            last_met_with_str = gettext("provider_dynamic_subtext_last_met")
            translated_last_date = format_date(last_date, "short")
            return f"{last_met_with_str} {translated_last_date}"
        else:
            return f'Last met with on {last_date.strftime("%m/%d/%y")}'

    elif provider_user.practitioner_profile.languages and not english_only_language:
        if l10n_flag:
            speaks_str = gettext("provider_dynamic_subtext_speaks")
            return f"{speaks_str} {format_languages(languages)}"
        else:
            return f"Speaks {format_languages(languages)}"
    else:
        return ""


def make_provider_search_result(
    provider_user: User,
    member_user: User,
    latest_appointment_date_by_provider_id: dict,
    l10n_flag: bool = False,
) -> dict:
    """This method takes a User (ORM object) and flattens it into
    a simple Python dict. We use a dataclass as part of the transformation
    just for some documentation and type validation.
    Developers should take care to ensure that all necessary fields on the
    User have already been joined in. In other words this method should emit 0 queries!
    You can use a debugger to step over the callsite and make sure that
    no SQL is echoed out during this step. If anything is emitted during
    this step, you have an n+1 query problem!
    """

    member_prescribable_state = member_user.member_profile.prescribable_state
    member_is_international = member_user.member_profile.is_international
    member_state_abbreviation = (
        member_user.member_profile.state.abbreviation
        if member_user.member_profile.state
        else ""
    )
    member_org_is_coaching_only = (
        member_user.organization.education_only if member_user.organization else False
    )

    verticals = provider_user.practitioner_profile.verticals
    provider_profile = provider_user.practitioner_profile
    can_prescribe = ProviderService().provider_can_prescribe_in_state(
        provider_profile, member_prescribable_state
    )
    next_availability = serialize_datetime(provider_profile.next_availability)
    provider_certified_states = provider_profile.certified_states
    certified_state_abbreviations = [s.abbreviation for s in provider_certified_states]

    if verticals:
        if l10n_flag:
            translated_vertical_name = TranslateDBFields().get_translated_vertical(
                verticals[0].slug, "name", default=verticals[0].name
            )
        else:
            translated_vertical_name = verticals[0].name
        appointment_type = ProviderService.get_provider_appointment_type_for_member(
            verticals[0].filter_by_state,
            member_state_abbreviation in certified_state_abbreviations,
            provider_profile.is_international,
            member_is_international,
            member_org_is_coaching_only,
        )
    else:
        translated_vertical_name = ""
        appointment_type = AppointmentTypes.EDUCATION_ONLY.value

    return asdict(
        ProviderSearchResultStruct(
            full_name=provider_user.full_name,
            name=provider_user.full_name,
            id=provider_user.id,
            image_url=provider_user.avatar_url,
            vertical=translated_vertical_name,
            can_prescribe=can_prescribe,
            next_availability=next_availability,
            dynamic_subtext=make_dynamic_subtext(
                provider_user,
                latest_appointment_date_by_provider_id,
                l10n_flag=l10n_flag,
            ),
            is_care_advocate=provider_user.practitioner_profile.is_cx,
            certified_states=certified_state_abbreviations,
            country_flag=get_provider_country_flag(provider_user.country_code),
            is_vertical_state_filtered=(
                verticals[0].filter_by_state if verticals else None
            ),
            appointment_type=appointment_type,
        )
    )


def get_cancellation_policy_text(obj, l10n_flag):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    policy = obj.cancellation_policy
    policy_name = policy.name.lower()
    if policy_name == "conservative":
        if l10n_flag:
            return gettext("cancellation_policy_explanation_conservative")
        return "50% refund if canceled at least 2 hours ahead of time"
    elif policy_name == "flexible":
        if l10n_flag:
            return gettext("cancellation_policy_explanation_flexible")
        return "Full refund if canceled at least 24 hours ahead of time"
    elif policy_name == "moderate":
        if l10n_flag:
            return gettext("cancellation_policy_explanation_moderate")
        return "50% refund if canceled at least 24 hours ahead of time"
    elif policy_name == "strict":
        if l10n_flag:
            return gettext("cancellation_policy_explanation_strict")
        return "No refund"
    else:
        return ""


def make_provider_profile_result(
    provider_user: User,
    member_user: User,
    latest_appointment_date_by_provider_id: dict,
    member_track_modifiers: List[TrackModifiers],
    client_track_ids: List[int],
    l10n_flag: bool = False,
) -> dict:
    provider_search_result = make_provider_search_result(
        provider_user,
        member_user,
        latest_appointment_date_by_provider_id,
        l10n_flag,
    )

    provider = provider_user.practitioner_profile
    verticals = provider_user.practitioner_profile.verticals
    if l10n_flag:
        tdbf = TranslateDBFields()

        return asdict(
            ProviderProfileStruct(
                can_request_availability=ProviderService().provider_contract_can_accept_availability_requests(
                    provider
                ),
                active=provider.active,
                certifications=[s.name for s in provider.certifications],
                messaging_enabled=provider.messaging_enabled,
                years_experience=provider.years_experience,
                education=(
                    [s.strip() for s in provider.education.split(",")]
                    if provider.education
                    else []
                ),
                work_experience=(
                    [s.strip() for s in provider.work_experience.split(",")]
                    if provider.work_experience
                    else []
                ),
                country=provider.country.name if provider.country else "",
                cancellation_policy=get_cancellation_policy_text(provider, l10n_flag),
                vertical_long_description=(
                    tdbf.get_translated_vertical(
                        verticals[0].slug,
                        "long_description",
                        default=verticals[0].long_description,
                    )
                    if verticals
                    else ""
                ),
                specialties=[
                    tdbf.get_translated_specialty(s.slug, "name", s.name)
                    for s in provider.specialties
                ],
                languages=[
                    tdbf.get_translated_language(l.slug, "name", l.name)
                    for l in provider.languages
                ],
                can_member_interact=ProviderService().provider_can_member_interact(
                    provider=provider,
                    modifiers=member_track_modifiers,
                    client_track_ids=client_track_ids,
                ),
                **provider_search_result,
            )
        )
    else:
        return asdict(
            ProviderProfileStruct(
                can_request_availability=ProviderService().provider_contract_can_accept_availability_requests(
                    provider
                ),
                active=provider.active,
                certifications=[s.name for s in provider.certifications],
                messaging_enabled=provider.messaging_enabled,
                years_experience=provider.years_experience,
                education=(
                    [s.strip() for s in provider.education.split(",")]
                    if provider.education
                    else []
                ),
                work_experience=(
                    [s.strip() for s in provider.work_experience.split(",")]
                    if provider.work_experience
                    else []
                ),
                country=provider.country.name if provider.country else "",
                cancellation_policy=get_cancellation_policy_text(provider, l10n_flag),
                vertical_long_description=verticals[0].long_description
                if verticals
                else "",
                specialties=[s.name for s in provider.specialties],
                languages=[l.name for l in provider.languages],
                can_member_interact=ProviderService().provider_can_member_interact(
                    provider=provider,
                    modifiers=member_track_modifiers,
                    client_track_ids=client_track_ids,
                ),
                **provider_search_result,
            )
        )
