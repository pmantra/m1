from __future__ import annotations

import enum
import typing
from typing import Any, Callable, Dict, List, TypeVar

from maven import feature_flags

from tasks.queues import job
from utils import log
from utils.transactional import only_on_successful_commit

if typing.TYPE_CHECKING:
    from authn.models.user import User
    from models.tracks.model import MemberTrack

logger = log.logger(__name__)

Handler = Callable[..., Any]
T = TypeVar("T", bound=Callable[..., Any])


class EventType(enum.Enum):
    INITIATE = "initiate"
    TRANSITION = "transition"
    TERMINATE = "terminate"


class EventManager:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Handler]] = {}

    def register(self, event_type: EventType, handler: Handler) -> None:
        event_type_str = event_type.value

        if event_type_str not in self._handlers:
            self._handlers[event_type_str] = []

        self._handlers[event_type_str].append(handler)
        logger.info(
            "Registered event handler",
            event_type=event_type_str,
            handler=handler.__name__,
        )

    def dispatch(self, event_type: EventType, **kwargs: Any) -> None:
        if feature_flags.bool_variation("disable-track-events-service", default=False):
            logger.warning(
                "Event system is disabled via feature flag. Skipping event dispatch.",
                event_type=event_type.value,
            )
            return

        event_type_str = event_type.value

        logger.info("Dispatching event", event_type=event_type_str)

        if event_type_str not in self._handlers:
            logger.info("No handlers registered for event", event_type=event_type_str)
            return

        for handler in self._handlers[event_type_str]:
            try:
                logger.info(
                    "Dispatching to handler",
                    handler=handler.__name__,
                    event_type=event_type_str,
                )
                self._dispatch_to_handler(handler, event_type, **kwargs)
            except Exception as e:
                logger.error(
                    "Error in dispatch loop for handler",
                    event_type=event_type_str,
                    error=str(e),
                    exc_info=e,
                )

    def _dispatch_to_handler(
        self, handler: Handler, event_type: EventType, **kwargs: Any
    ) -> None:
        execute_handler.delay(handler.__name__, event_type.value, **kwargs)


event_manager = EventManager()


@job(team_ns="enrollments")
def execute_handler(handler_name: str, event_type_str: str, **kwargs: Any) -> None:
    try:
        handler = handler_registry.get(handler_name)
        if handler is None:
            logger.error(
                "Handler not found in registry",
                handler_name=handler_name,
                event_type=event_type_str,
            )
            return

        logger.info(
            "Executing event handler",
            handler_name=handler_name,
            event_type=event_type_str,
        )
        handler(**kwargs)
        logger.info(
            "Handler execution completed successfully",
            handler_name=handler_name,
            event_type=event_type_str,
        )
    except Exception as e:
        logger.error(
            "Error executing event handler",
            handler_name=handler_name,
            event_type=event_type_str,
            error=str(e),
            exc_info=e,
        )


handler_registry: Dict[str, Handler] = {}


def event_handler(event_type: EventType) -> Callable[[T], T]:
    def decorator(func: T) -> T:
        event_manager.register(event_type, func)
        handler_registry[func.__name__] = func

        return func

    return decorator


@only_on_successful_commit
def dispatch_initiate_event(track: MemberTrack, user: User) -> None:
    event_manager.dispatch(EventType.INITIATE, track_id=track.id, user_id=user.id)


@only_on_successful_commit
def dispatch_transition_event(
    source_track: MemberTrack, target_track: MemberTrack, user: User
) -> None:
    event_manager.dispatch(
        EventType.TRANSITION,
        source_track_id=source_track.id,
        target_track_id=target_track.id,
        user_id=user.id,
    )


@only_on_successful_commit
def dispatch_terminate_event(track: MemberTrack, user: User) -> None:
    event_manager.dispatch(EventType.TERMINATE, track_id=track.id, user_id=user.id)
