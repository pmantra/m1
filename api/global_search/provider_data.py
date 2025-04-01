from __future__ import annotations

import datetime
import json

from sqlalchemy.orm import joinedload, subqueryload

from appointments.models.needs_and_categories import Need
from appointments.schemas.provider import make_dynamic_subtext
from appointments.utils.provider import get_provider_country_flag
from authn.models.user import User
from models.profiles import PractitionerData, PractitionerProfile
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job("priority", team_ns="ai_platform")
def update_practitioners_data(batch_size=50):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("Start reading profiles and needs data")
    profiles = (
        db.session.query(PractitionerProfile)
        .options(
            subqueryload(PractitionerProfile.verticals),
            subqueryload(PractitionerProfile.specialties),
            subqueryload(PractitionerProfile.languages),
        )
        .all()
    )
    practitioner_data_list = db.session.query(PractitionerData).all()
    practitioner_data_dict = {
        practitioner_data.user_id: practitioner_data
        for practitioner_data in practitioner_data_list
    }
    needs = (
        db.session.query(Need)
        .options(
            subqueryload(Need.verticals),
            subqueryload(Need.specialties),
            subqueryload(Need.restricted_verticals),
            subqueryload(Need.categories),
        )
        .all()
    )
    practitioner_users = (
        db.session.query(User)
        .options(
            joinedload(User.image),
        )
        .join(PractitionerProfile)
        .all()
    )
    practitioner_users_dict = {user.id: user for user in practitioner_users}
    log.info(
        f"Processing {len(profiles)} practitioner profiles and {len(needs)} needs."
    )

    # Populate profiles/verticals/specialties/needs
    idx = 0
    processed_data_list = []
    for profile in profiles:
        idx += 1
        practitioner_user = practitioner_users_dict[profile.user_id]
        practitioner_user.practitioner_profile = profile
        # Update practitioner_data if we have the profile
        if profile.user_id in practitioner_data_dict:
            practitioner_data = practitioner_data_dict[profile.user_id]
            practitioner_data.practitioner_profile_json = json.dumps(
                construct_profile_json(profile, practitioner_user)
            )
            practitioner_data.practitioner_profile_modified_at = datetime.datetime.now(
                datetime.timezone.utc
            )
            practitioner_data.next_availability = profile.next_availability
            practitioner_data.vertical_json = json.dumps(
                [construct_vertical_json(vertical) for vertical in profile.verticals]
            )
            practitioner_data.vertical_modified_at = datetime.datetime.now(
                datetime.timezone.utc
            )
            practitioner_data.specialty_json = json.dumps(
                [
                    construct_specialty_json(specialty)
                    for specialty in profile.specialties
                ]
            )
            practitioner_data.specialty_modified_at = datetime.datetime.now(
                datetime.timezone.utc
            )
            practitioner_data.need_json = json.dumps(
                construct_needs_json(profile, needs)
            )
            practitioner_data.need_modified_at = datetime.datetime.now(
                datetime.timezone.utc
            )
            processed_data_list.append(practitioner_data)
        # Add practitioner_data if we don't have
        else:
            new_practitioner_data = PractitionerData(
                user_id=profile.user_id,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                practitioner_profile_json=json.dumps(
                    construct_profile_json(profile, practitioner_user)
                ),
                practitioner_profile_modified_at=datetime.datetime.now(
                    datetime.timezone.utc
                ),
                next_availability=profile.next_availability,
                vertical_json=json.dumps(
                    [
                        construct_vertical_json(vertical)
                        for vertical in profile.verticals
                    ]
                ),
                vertical_modified_at=datetime.datetime.now(datetime.timezone.utc),
                specialty_json=json.dumps(
                    [
                        construct_specialty_json(specialty)
                        for specialty in profile.specialties
                    ]
                ),
                specialty_modified_at=datetime.datetime.now(datetime.timezone.utc),
                need_json=json.dumps(construct_needs_json(profile, needs)),
                need_modified_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.session.add(new_practitioner_data)
            processed_data_list.append(new_practitioner_data)

        # batch commit and expunge to avoid OOM
        if idx % batch_size == 0:
            db.session.commit()
            for p_data in processed_data_list:
                db.session.expunge(p_data)
            processed_data_list = []
            log.info(f"Committing {idx} records")

    db.session.commit()


def construct_profile_json(profile_obj, user_obj) -> dict:  # type: ignore
    if not profile_obj:
        return {}

    return {
        "user_id": profile_obj.user_id,
        "active": profile_obj.active,
        "role_id": profile_obj.role_id,
        "stripe_account_id": profile_obj.stripe_account_id,
        "default_cancellation_policy_id": profile_obj.default_cancellation_policy_id,
        "phone_number": profile_obj.phone_number,
        "reference_quote": profile_obj.reference_quote,
        "state_id": profile_obj.state_id,
        "education": profile_obj.education,
        "work_experience": profile_obj.work_experience,
        "awards": profile_obj.awards,
        "dosespot": profile_obj.dosespot,
        "booking_buffer": profile_obj.booking_buffer,
        "default_prep_buffer": profile_obj.default_prep_buffer,
        "show_when_unavailable": profile_obj.show_when_unavailable,
        "messaging_enabled": profile_obj.messaging_enabled,
        "response_time": profile_obj.response_time,
        "anonymous_allowed": profile_obj.anonymous_allowed,
        "ent_national": profile_obj.ent_national,
        "is_staff": profile_obj.is_staff,
        "rating": profile_obj.rating,
        "zendesk_email": profile_obj.zendesk_email,
        "show_in_marketplace": profile_obj.show_in_marketplace,
        "show_in_enterprise": profile_obj.show_in_enterprise,
        "json": profile_obj.json,
        "experience_started": (
            profile_obj.experience_started.strftime("%Y-%m-%d")
            if profile_obj.experience_started
            else None
        ),
        "billing_org": (
            profile_obj.billing_org.value if profile_obj.billing_org else None
        ),
        "credential_start": (
            profile_obj.credential_start.strftime("%Y-%m-%d %H:%M:%S")
            if profile_obj.credential_start
            else None
        ),
        "note": profile_obj.note,
        "first_name": profile_obj.first_name,
        "middle_name": profile_obj.middle_name,
        "last_name": profile_obj.last_name,
        "username": profile_obj.username,
        "timezone": profile_obj.timezone,
        "country_code": profile_obj.country_code,
        "country_flag": (
            get_provider_country_flag(profile_obj.country_code)
            if profile_obj.country_code
            else None
        ),
        "subdivision_code": profile_obj.subdivision_code,
        "email": profile_obj.email,
        "dynamic_subtext": make_dynamic_subtext(user_obj, {}, True),
        "image_url": user_obj.avatar_url,
    }


def construct_vertical_json(vertical_obj) -> dict:  # type: ignore
    if not vertical_obj:
        return {}

    return {
        "id": vertical_obj.id,
        "name": vertical_obj.name,
        "description": vertical_obj.description,
        "display_name": vertical_obj.display_name,
        "pluralized_display_name": vertical_obj.pluralized_display_name,
        "filter_by_state": vertical_obj.filter_by_state,
        "can_prescribe": vertical_obj.can_prescribe,
        "products": vertical_obj.products,
        "long_description": vertical_obj.long_description,
        "slug": vertical_obj.slug,
        "searchable_localized_data": vertical_obj.searchable_localized_data,
    }


def construct_specialty_json(specialty_obj) -> dict:  # type: ignore
    if not specialty_obj:
        return {}

    return {
        "id": specialty_obj.id,
        "name": specialty_obj.name,
        "image_id": specialty_obj.image_id,
        "ordering_weight": specialty_obj.ordering_weight,
        "slug": specialty_obj.slug,
        "searchable_localized_data": specialty_obj.searchable_localized_data,
    }


def construct_single_need_json(need_obj) -> dict:  # type: ignore
    if not need_obj:
        return {}

    return {
        "id": need_obj.id,
        "name": need_obj.name,
        "description": need_obj.description,
        "display_order": need_obj.display_order,
        "promote_messaging": need_obj.promote_messaging,
        "hide_from_multitrack": need_obj.hide_from_multitrack,
        "slug": need_obj.slug,
        "searchable_localized_data": need_obj.searchable_localized_data,
    }


def construct_need_category_json(need_category_obj) -> dict:  # type: ignore
    if not need_category_obj:
        return {}

    return {
        "id": need_category_obj.id,
        "name": need_category_obj.name,
        "description": need_category_obj.description,
        "parent_category_id": need_category_obj.parent_category_id,
        "display_order": need_category_obj.display_order,
        "image_id": need_category_obj.image_id,
        "hide_from_multitrack": need_category_obj.hide_from_multitrack,
        "slug": need_category_obj.slug,
        "searchable_localized_data": need_category_obj.searchable_localized_data,
    }


def construct_needs_json(practitioner_profile, needs) -> dict:  # type: ignore
    matched_needs = []
    need_categories_dict = {}

    for need in needs:
        if not match_practitioner_and_need(practitioner_profile, need):
            continue

        # Add the need to the matched needs list
        matched_needs.append(construct_single_need_json(need))

        # Add associated need categories and de-dup
        for need_category in need.categories:
            need_categories_dict.setdefault(need_category.id, need_category)

    return {
        "needs": matched_needs,
        "need_categories": [
            construct_need_category_json(need_category)
            for need_category in need_categories_dict.values()
        ],
    }


def match_practitioner_and_need(practitioner_profile, need) -> bool:  # type: ignore
    """
    Returns: True if the practitioner meets the requirements of the need. False otherwise.
    """
    # Vertical match: at least one
    need_vertical_ids = {vertical.id for vertical in need.verticals}
    practitioner_vertical_ids = {
        vertical.id for vertical in practitioner_profile.verticals
    }
    vertical_intersection = need_vertical_ids & practitioner_vertical_ids
    if not vertical_intersection:
        return False

    practitioner_specialty_ids = {
        specialty.id for specialty in practitioner_profile.specialties
    }
    # If the need has specialties, run the matching: at least one
    if need.specialties:
        need_specialty_ids = {specialty.id for specialty in need.specialties}
        specialty_intersection = need_specialty_ids & practitioner_specialty_ids
        if not specialty_intersection:
            return False

    # If the need has NeedRestrictedVerticals, run the speciality matching: at least one
    if need.restricted_verticals:
        nrv_specialty_ids = {nrv.specialty_id for nrv in need.restricted_verticals}
        nrv_specialty_intersection = nrv_specialty_ids & practitioner_specialty_ids
        if not nrv_specialty_intersection:
            return False

    return True
