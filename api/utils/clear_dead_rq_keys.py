import time
from typing import Iterator, List

import dateparser

from utils import log
from utils.cache import redis_client

MATCH_PATTERN = "rq:job:*"
PAGE_LIMIT = 50

logger = log.logger("rq-key-invalidator")


class RQKeyInvalidator:
    """A class with methods for cleaning up useless keys in redis created by RQ

    Note:
        RQ v1.0 has some bugs that cause dead jobs to linger in redis storage indefinitely.
        Over time the volume of keys causes us to have to increase the memory limit on that instance to continue to serve requests.

    Parameters:
        redis: A Redis client
        timestamp: Only collect keys that ended before this date
        batch_size (int): The COUNT provided to the redis SCAN call
        page_limit (int): Limit the number of SCANs that we will do
        throttle (int): Time in seconds to sleep between SCANs
    """

    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        *,
        redis=None,
        timestamp=None,
        batch_size=250,
        page_limit=None,
        throttle=None,
    ):
        self.redis = redis or redis_client(decode_responses=True)
        self.batch_size = batch_size
        self.timestamp = timestamp or self.parse_date("1 week ago UTC")
        self.page_limit = page_limit or PAGE_LIMIT
        self.throttle = throttle

    def process_deletion(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Spins through all of the keys matching MATCH_PATTERN and deletes those keys if they are old, failed jobs"""
        logger.info("Beginning purging deleteable redis keys.")
        for keys in self.get_all_keys():
            logger.info(f"Deleting {len(keys)} redis keys")
            deleteable, _ = self.deleteable_keys(keys)
            self.remove_keys(deleteable)

    def percent_deleteable(self) -> float:
        """Get a count of the number of keys that could be deleted for the MATCH_PATTERN"""
        logger.info("Beginning finding deleteable redis keys.")
        deleteable = 0
        not_deleteable = 0
        for keys in self.get_all_keys():
            can, cannot = self.deleteable_keys(keys)
            deleteable += len(can)
            not_deleteable += len(cannot)
        total = deleteable + not_deleteable
        if total > 0:
            return (deleteable / total) * 100
        else:
            return 0.0

    def deleteable_keys(self, keys: List[str]) -> (List[str], List[str]):  # type: ignore[syntax] # Syntax error in type annotation
        """Filters keys to find those that are both in the past and in a failed state"""
        deleteable = []
        not_deleteable = []
        logger.info("Identifying which keys can be deleted")
        with self.redis.pipeline(transaction=False) as pipe:
            for key in keys:
                pipe.type(key)

            types = pipe.execute()
            keys_to_type = dict(zip(keys, types))

            keys_to_check = [
                k
                for k, t in keys_to_type.items()
                if t == "hash" or not_deleteable.append(k)  # type: ignore[func-returns-value] # "append" of "list" does not return a value (it only ever returns None)
            ]
            with self.redis.pipeline(transaction=False) as pipe:
                for key in keys_to_check:
                    pipe.hmget(key, "ended_at", "status")

                fields = pipe.execute()
                keys_to_fields = dict(zip(keys, fields))

            for key, (ended_at, status) in keys_to_fields.items():
                in_date_range = ended_at and (
                    self.parse_date(ended_at) < self.timestamp
                )
                if in_date_range and status == "failed":
                    deleteable.append(key)
                    continue

                not_deleteable.append(key)
            return deleteable, not_deleteable

    def remove_keys(self, keys: List[str]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if len(keys) > 0:
            self.redis.delete(*keys)

    def get_all_keys(self) -> Iterator[List[str]]:
        cursor = 0
        continue_scanning = True
        scans = 0
        while continue_scanning:
            cursor, keys = self.get_keys(cursor=cursor, batch_size=self.batch_size)
            yield keys
            # redis SCAN will return a cursor of 0 once the full iteration has been completed
            if cursor == 0 or scans > self.page_limit:
                continue_scanning = False
            scans += 1
            if self.throttle:
                logger.info(f"Sleeping for {self.throttle} seconds")
                time.sleep(self.throttle)

    def get_keys(self, *, cursor: int, batch_size: int) -> (int, List[str]):  # type: ignore[syntax] # Syntax error in type annotation
        logger.info("Scanning for keys")
        result = self.redis.scan(cursor, MATCH_PATTERN, batch_size)
        return result[0], result[1]

    def parse_date(self, datestring):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return dateparser.parse(datestring, settings={"TIMEZONE": "UTC"})
