from __future__ import annotations

from authn.models.user import REDIS_SESSIONS_HOST
from utils import cache, log

logger = log.logger("sessions-migration")


def migrate_session_keys() -> list:
    logger.info("Beginning migration of session keys.")
    logger.debug("Connecting to redis.", host=REDIS_SESSIONS_HOST)
    redis = cache.redis_client(REDIS_SESSIONS_HOST, decode_responses=True)
    sessions = redis.keys("session:*:*")
    logger.info("Found existing sessions.", sessions=len(sessions))
    session_key_to_user: dict[str, tuple[str, int]] = {}
    user_key_to_sessions: dict[str, set] = {}
    for key in sessions:
        ttl = redis.ttl(key)
        _, uid, sid = key.rsplit(":")
        if uid in {"user_id", "id"}:
            logger.debug("Found a new-style session key, skipping.", key=key)
            continue
        session_key_to_user[f"session:id:{sid}"] = (uid, ttl)
        user_key_to_sessions.setdefault(f"session:user_id:{uid}", set()).add(sid)
    logger.info("Mapped session ids and user ids.")
    logger.info("Migrating sessions.")
    with redis.pipeline(transaction=False) as pipe:
        logger.debug("Setting session-key lookup for locating user ids.")
        for key, (uid, ttl) in session_key_to_user.items():
            pipe.setex(key, ttl, uid)
        logger.debug("Setting reverse lookups.")
        for ukey, seshs in user_key_to_sessions.items():
            pipe.sadd(ukey, *seshs)
        logger.debug("Executing redis commands.")
        results = pipe.execute()
    logger.info("Done migrating session keys.")
    return results
