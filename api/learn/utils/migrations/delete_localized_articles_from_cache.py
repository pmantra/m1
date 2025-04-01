"""
delete_localized_articles_from_cache.py

deletes localized (non-english) articles from the cache, since they may include reviewers + related reads

Usage:
    delete_localized_articles_from_cache.py [--dry-run]
"""
import os

os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["DEV_LOGGING"] = "1"

from docopt import docopt

from app import create_app
from learn.services.caching_service import CachingService
from utils.log import logger

log = logger(__name__)


def delete_localized_articles_from_cache(dry_run: bool) -> None:
    learn_cache = CachingService()
    if not learn_cache.redis_client:
        log.error("Redis is not defined in this environment")
        exit(1)

    key_pattern = "article:*:*"
    keys = learn_cache.redis_client.keys(key_pattern)
    keys_to_delete = [key for key in keys if not key.startswith("article:en")]
    if not keys_to_delete:
        log.debug("No keys to delete")
    elif dry_run:
        for key in keys_to_delete:
            log.debug(f"Would've deleted key [{key}]")
    else:
        pipeline = learn_cache.redis_client.pipeline()
        for key in keys_to_delete:
            pipeline.delete(key)
            log.debug(f"Deleting key [{key}]")
        pipeline.execute()


if __name__ == "__main__":
    args = docopt(__doc__)
    dry_run = args["--dry-run"]
    with create_app().app_context():
        delete_localized_articles_from_cache(dry_run=dry_run)
