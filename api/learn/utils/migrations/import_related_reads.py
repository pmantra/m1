"""
import_to_contentful.py

Takes a file consisting of a JSON object with string resource ids as keys and
Contentful entry representations as values.  Fetches the corresponding info
for each entry's related reads, then uploads the related reads to Contentful.

Usage:
    import_to_contentful.py (--filename=<filename>)

Options:
  --filename=<filename>         Provide a filename under the utils/migrations/webflow folder to read from
"""

import hashlib
import json

import contentful_management
import docopt
from sqlalchemy import orm

from app import create_app
from learn.utils.migrations import constants, import_to_contentful
from models import marketing
from storage.connection import db
from utils.log import logger

log = logger(__name__)

client = contentful_management.Client(constants.CONTENTFUL_MANAGEMENT_KEY)
environment = client.environments(constants.CONTENTFUL_SPACE_ID).find(
    constants.CONTENTFUL_ENVIRONMENT_ID
)


def import_related_reads_to_contentful(filename):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with open(f"learn/utils/migrations/{filename}") as f:
        resources = json.load(f)
    for string_id, entry_obj in resources.items():
        try:
            related_reads = get_related_reads_from_contentful_or_db(entry_obj)
            entry_obj["fields"]["relatedReads"]["en-US"] = related_reads
            entry_id = hashlib.md5(
                entry_obj["fields"]["slug"]["en-US"].encode()
            ).hexdigest()
            entry = import_to_contentful.contentful_entry_or_none(entry_id)
            if entry:
                entry.related_reads = related_reads
                entry.save()
                entry.publish()
                log.info(
                    "Updated contentful entry and its related reads",
                    resource_id=string_id,
                    entry_id=entry_id,
                )
            else:
                log.warn(
                    "Contentful entry not found when updating related reads",
                    resource_id=string_id,
                    entry_id=entry_id,
                )
        except Exception as e:
            log.error(
                "Error creating or updating related reads for resource",
                resource_id=string_id,
                error=e,
            )
            db.session.rollback()


def get_related_reads_from_contentful_or_db(entry_obj: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    related_reads = []
    for slug in entry_obj["fields"]["relatedReads"]["en-US"]:
        # Try to get Contentful article entry
        related_article_entry_id = hashlib.md5(slug.encode()).hexdigest()
        related_article_entry = import_to_contentful.contentful_entry_or_none(
            related_article_entry_id
        )
        if related_article_entry:
            related_reads.append(contentful_link_dict(related_article_entry_id))
        else:
            log.debug("Related article not found in Contentful; trying db", slug=slug)
            resource = (
                db.session.query(marketing.Resource)
                .filter_by(slug=slug)
                .options(orm.load_only(marketing.Resource.slug))
                .one_or_none()
            )
            # To prevent "Lost connection to MySQL server during query" error
            db.session.commit()

            if resource:
                noncontentful_article_entry_id = hashlib.md5(
                    (slug + "related-read").encode()
                ).hexdigest()
                existing_entry = import_to_contentful.contentful_entry_or_none(
                    noncontentful_article_entry_id
                )
                if not existing_entry:
                    log.info("Creating Non-Contentful Article entry", slug=slug)
                    entry = environment.entries().create(
                        noncontentful_article_entry_id,
                        {
                            "content_type_id": "nonContentfulArticle",
                            "fields": {
                                "title": {"en-US": resource.title},
                                "slug": {"en-US": resource.slug},
                            },
                        },
                    )
                    entry.publish()
                related_reads.append(
                    contentful_link_dict(noncontentful_article_entry_id)
                )
            else:
                log.warn("Related article not found in db", slug=slug)
    return related_reads


def contentful_link_dict(entry_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return {
        "sys": {
            "type": "Link",
            "linkType": "Entry",
            "id": entry_id,
        },
    }


if __name__ == "__main__":
    args = docopt.docopt(__doc__)
    with create_app().app_context():
        import_related_reads_to_contentful(args["--filename"])
