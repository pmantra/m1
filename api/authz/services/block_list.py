from __future__ import annotations

from typing import TYPE_CHECKING

from redis.exceptions import ConnectionError, TimeoutError

from authn.domain.service import user
from common import stats
from storage.connection import db
from utils.cache import redis_client
from utils.log import logger

if TYPE_CHECKING:
    from redis import Redis

log = logger(__name__)

USER_BLOCKED_ATTRIBUTES_KEY = "user_blocked_attributes"

BlockableAttributes = frozenset(["phone_number", "credit_card"])


class BlockList:
    """Manage a set of attributes for users that will prevent them from accessing their account"""

    _skip_if_unavailable: bool
    redis: Redis

    def __init__(self, skip_if_unavailable=False, timeout=5.0):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        if skip_if_unavailable is True then the check will be the best effort attempt
        """
        self._skip_if_unavailable = skip_if_unavailable
        self.redis = redis_client(
            decode_responses=True,
            socket_timeout=timeout,
        )

    def validate_access(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        user_id: int,
        attribute: BlockableAttributes,  # type: ignore[valid-type] # Variable "authz.services.block_list.BlockableAttributes" is not valid as a type
        check_values: str | list[str],
    ):
        if isinstance(check_values, str):
            check_values = [check_values]

        self._validate_attribute(attribute)

        try:
            if any(
                self.redis.sismember(self._key(attribute), value)
                for value in check_values
            ):
                log.info(
                    f"Preventing access for user in blocked attributes list: user_id={user_id}"
                )
                self._disable_user(user_id)
                raise BlockListDenied(
                    f"User blocked:{attribute} denied for value {check_values}"
                )
        except BlockListDenied:
            # intended behavior when denied
            raise
        except TimeoutError as timeout_ex:
            log.warning(
                "BlockList settings timeout when connecting to redis",
                exception=timeout_ex,
            )
            stats.increment(
                "mono.block_list.error",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[
                    "error:timeout",
                    f"skip_if_unavailable:{self._skip_if_unavailable}",
                ],
            )
        except ConnectionError as connect_ex:
            log.warning(
                "BlockList connection error when connecting to redis",
                exception=connect_ex,
            )
            stats.increment(
                "mono.block_list.error",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[
                    "error:connection",
                    f"skip_if_unavailable:{self._skip_if_unavailable}",
                ],
            )
        except ConnectionRefusedError as connection_refused_ex:
            log.warning(
                "BlockList connection refused error when connecting to redis",
                exception=connection_refused_ex,
            )
            stats.increment(
                "mono.block_list.error",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[
                    "error:connection_refused",
                    f"skip_if_unavailable:{self._skip_if_unavailable}",
                ],
            )
        except Exception as e:
            log.warning("BlockList error when connecting to redis", exception=e)
            stats.increment(
                "mono.block_list.error",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[
                    "error:unidentified",
                    f"skip_if_unavailable:{self._skip_if_unavailable}",
                ],
            )
            # re-throw the error if not to ignore otherwise swallow
            if not self._skip_if_unavailable:
                raise e

    def block_attribute(self, attribute: BlockableAttributes, value: str):  # type: ignore[valid-type,no-untyped-def] # Variable "authz.services.block_list.BlockableAttributes" is not valid as a type #type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Add another item to the block list for a given user attribute"""
        self._validate_attribute(attribute)
        self.redis.sadd(self._key(attribute), value)

    def unblock_attribute(self, attribute: BlockableAttributes, value: str):  # type: ignore[valid-type,no-untyped-def] # Variable "authz.services.block_list.BlockableAttributes" is not valid as a type #type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Remove an item from the block list for a given user attribute"""
        self._validate_attribute(attribute)
        self.redis.srem(self._key(attribute), value)

    def get_block_list(self, attribute: BlockableAttributes):  # type: ignore[valid-type,no-untyped-def] # Variable "authz.services.block_list.BlockableAttributes" is not valid as a type #type: ignore[no-untyped-def] # Function is missing a return type annotation
        """View all of the blocked values for a given user attribute"""
        self._validate_attribute(attribute)
        return list(self.redis.smembers(self._key(attribute)))

    def _key(self, attribute: str) -> str:
        return f"{USER_BLOCKED_ATTRIBUTES_KEY}.{attribute}"

    def _disable_user(self, user_id: int) -> None:
        user_service = user.UserService()
        user_service.update_user(user_id=user_id, is_active=False)
        db.session.commit()

    def _validate_attribute(self, attribute: BlockableAttributes):  # type: ignore[valid-type,no-untyped-def] # Variable "authz.services.block_list.BlockableAttributes" is not valid as a type #type: ignore[no-untyped-def] # Function is missing a return type annotation
        if attribute not in BlockableAttributes:
            raise AttributeError(
                f"Attribute '{attribute}' not permitted by BlockableAttributes. Select from: {', '.join(BlockableAttributes)}"
            )


# This exception should be raised all the way up to our ExceptionAwareApi where it is handled
class BlockListDenied(Exception):
    ...
