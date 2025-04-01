from __future__ import annotations

from sqlalchemy import distinct

from authn.models.user import User
from braze import BrazeClient, BrazeExportedUser, BrazeUserAttributes, client
from braze.client.utils import compare_to_braze_profile
from models.tracks import MemberTrack
from storage.connection import db
from tasks.queues import job
from utils.braze import _populate_last_track_attrs, _populate_track_attrs
from utils.log import logger

log = logger(__name__)


def get_user_ids_with_active_track_query():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return (
        db.session.query(distinct(User.id))
        .join(
            MemberTrack,
            User.id == MemberTrack.user_id,
        )
        .filter(MemberTrack.active.is_(True))
    )


def get_user_ids_with_active_track_count():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return get_user_ids_with_active_track_query().count()


def build_user_track_attrs(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user: User,
) -> client.BrazeUserAttributes:

    user_attrs = {"email": user.email}

    if user.active_tracks:
        _populate_track_attrs(user_attrs, user)

    _populate_last_track_attrs(user_attrs, user)

    return client.BrazeUserAttributes(external_id=user.esp_id, attributes=user_attrs)


def get_mismatched_braze_user(*, user: User) -> list[BrazeUserAttributes]:
    braze_client = BrazeClient()

    users_to_update = []
    try:
        user_attributes: BrazeUserAttributes = build_user_track_attrs(user=user)
        braze_profile: BrazeExportedUser | None = braze_client.fetch_user(
            external_id=user.esp_id
        )

        attributes_to_update: BrazeUserAttributes | None = None
        if braze_profile is None:
            log.info(
                "Braze profile not found. Skipping.",
                external_id=user.esp_id,
            )
        else:
            attributes_to_update = compare_to_braze_profile(
                user_attributes=user_attributes,
                braze_profile=braze_profile,
            )

        if attributes_to_update:
            users_to_update.append(attributes_to_update)
    except Exception as e:
        log.error(
            "Error while fetching user attributes: {}".format(e),
            external_id=user.esp_id,
        )

    return users_to_update


@job(team_ns="enrollments", service_ns="tracks")
def backfill_braze_profile_tracks_coordinator(page_size: int = 100, page_limit: int = 1_000, run_async: bool = False, update_braze: bool = False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(
        "Running backfill_braze_profile_tracks",
        page_size=page_size,
        page_limit=page_limit,
    )

    users_count = get_user_ids_with_active_track_count()
    all_pages = int(users_count / page_size) + 1
    pages = min(page_limit, all_pages)

    log.info(
        "Coordinating creation of backfill_braze_profile_tracks jobs",
        users_count=users_count,
        all_pages=all_pages,
        pages=pages,
    )

    for page in range(pages):
        if run_async:
            backfill_braze_profile_tracks.delay(
                page=page, page_size=page_size, update_braze=update_braze
            )
        else:
            backfill_braze_profile_tracks(
                page=page, page_size=page_size, update_braze=update_braze
            )


@job(team_ns="enrollments", service_ns="tracks")
def backfill_braze_profile_tracks(page: int = 0, page_size: int = 100, update_braze: bool = False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(
        "Comparing braze profiles for members with active tracks",
        page=page,
        page_size=page_size,
    )

    user_ids_with_active_track = (
        res[0]
        for res in (
            get_user_ids_with_active_track_query()
            .order_by(User.id)
            .limit(page_size)
            .offset(page * page_size)
        )
    )

    stats = {}

    users = User.query.filter(User.id.in_(user_ids_with_active_track)).all()

    for user in users:
        handle_backfill_braze_profile_tracks(
            user=user, stats=stats, update_braze=update_braze
        )

    log.info(
        "Finished comparing braze profiles for members with active tracks.",
        page=page,
        page_size=page_size,
        stats=stats,
    )


def handle_backfill_braze_profile_tracks(
    user: User, stats: dict[str, int], update_braze: bool = False
) -> None:
    attrs = get_mismatched_braze_user(user=user)

    for attr in attrs:
        for key in attr.attributes:
            stats[key] = stats[key] + 1 if key in stats else 1

    if update_braze and attrs:
        log.info("Updating braze profile attributes.", attrs=attrs)
        braze_client = BrazeClient()
        return braze_client.track_users(user_attributes=attrs)
    return None


def backfill(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    page_size: int = 100,
    page_limit: int = 1_000,
    run_async: bool = False,
    update_braze: bool = False,
):
    log.info(
        "Running braze profile tracks backfill",
        page_limit=page_limit,
        page_size=page_size,
        run_async=run_async,
        update_braze=update_braze,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        if run_async:
            backfill_braze_profile_tracks_coordinator.delay(
                page_size=page_size,
                page_limit=page_limit,
                run_async=run_async,
                update_braze=update_braze,
            )
        else:
            backfill_braze_profile_tracks_coordinator(
                page_size=page_size,
                page_limit=page_limit,
                run_async=run_async,
                update_braze=update_braze,
            )
