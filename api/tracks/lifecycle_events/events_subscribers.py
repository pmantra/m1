from braze.client.utils import send_braze_event
from models.tracks import MemberTrack
from tracks.lifecycle_events.event_system import EventType, event_handler

TRACK_SELECTION_BRAZE_EVENT = "test_track_selection_completed"
SECOND_TRACK_SELECTION_BRAZE_EVENT = "test_second_track_selection_completed"
from utils import log

logger = log.logger(__name__)


@event_handler(event_type=EventType.INITIATE)
def handle_track_initiation_example(track_id: int, user_id: int) -> None:
    track = MemberTrack.query.filter_by(id=track_id).first()

    logger.info(
        "Track initiated event handler",
        track_id=track_id,
        user_id=user_id,
        track_name=track.name,
    )


@event_handler(event_type=EventType.INITIATE)
def send_braze_event_after_track_initiation(track_id: int, user_id: int) -> None:

    track = MemberTrack.query.filter_by(id=track_id).first()
    # query active tracks order by created_at
    active_tracks = (
        MemberTrack.query.filter(
            MemberTrack.user_id == user_id, MemberTrack.active.is_(True)
        )
        .order_by(MemberTrack.created_at)
        .all()
    )

    if len(active_tracks) == 2:
        first_track = active_tracks[0]
        second_track = active_tracks[1]

        send_braze_event(
            external_id=str(second_track.id),
            event_name=SECOND_TRACK_SELECTION_BRAZE_EVENT,
            properties={
                "first_track": first_track.name,
                "second_track": second_track.name,
            },
        )
        logger.info(
            "[BRAZE] Second track selection event sent",
            user_id=user_id,
            track_id=second_track.id,
            track_name=second_track.name,
        )
    elif len(active_tracks) == 1:
        count_track_type = MemberTrack.query.filter(
            MemberTrack.user_id == user_id, MemberTrack.name == track.name
        ).count()
        inactive_tracks_count = MemberTrack.query.filter(
            MemberTrack.user_id == user_id, MemberTrack.active.is_(False)
        ).count()
        # send out event only when it was not registered before
        if count_track_type == 1 and inactive_tracks_count > 0:
            send_braze_event(
                external_id=str(track_id),
                event_name=TRACK_SELECTION_BRAZE_EVENT,
                properties={
                    "primary_track": track.name,
                    "secondary_track": None,
                    "multitrack_at_onboarding": False,
                },
            )
            logger.info(
                "[BRAZE] Track selection event sent",
                user_id=user_id,
                track_id=track_id,
                track_name=track.name,
            )
    else:
        logger.error(
            "[BRAZE] Unexpected number of active tracks",
            user_id=user_id,
            active_tracks_count=len(active_tracks),
        )


@event_handler(event_type=EventType.TRANSITION)
def send_braze_event_after_track_transition(
    source_track_id: int, target_track_id: int, user_id: int
) -> None:
    source_track = MemberTrack.query.filter_by(id=source_track_id).first()
    target_track = MemberTrack.query.filter_by(id=target_track_id).first()

    send_braze_event(
        external_id=str(target_track.id),
        event_name=TRACK_SELECTION_BRAZE_EVENT,
        properties={
            "primary_track": target_track.name,
            "last_track": source_track.name,
            "multitrack_at_onboarding": False,
            "secondary_track": None,
        },
    )
    logger.info(
        "[BRAZE] Track selection transition event sent",
        user_id=user_id,
        source_track_id=source_track_id,
        target_track_id=target_track_id,
        source_track_name=source_track.name,
        target_track_name=target_track.name,
    )


@event_handler(event_type=EventType.TRANSITION)
def handle_track_transition_example(
    source_track_id: int,
    target_track_id: int,
    user_id: int,
) -> None:
    from utils import log

    logger = log.logger(__name__)
    source_track = MemberTrack.query.filter_by(id=source_track_id).first()
    target_track = MemberTrack.query.filter_by(id=target_track_id).first()

    logger.info(
        "Track transition event handler",
        source_track_id=source_track_id,
        target_track_id=target_track_id,
        user_id=user_id,
        source_track_name=source_track.name,
        target_track_name=target_track.name,
    )


@event_handler(event_type=EventType.TERMINATE)
def handle_track_termination_example(track_id: int, user_id: int) -> None:
    from utils import log

    logger = log.logger(__name__)
    track = MemberTrack.query.filter_by(id=track_id).first()

    logger.info(
        "Track terminated event handler",
        track_id=track_id,
        user_id=user_id,
        track_name=track.name,
    )
