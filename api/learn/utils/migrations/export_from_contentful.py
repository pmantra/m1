from datetime import datetime

from sqlalchemy.dialects import mysql

from app import create_app
from learn.models.migration import ContentfulMigrationStatus
from learn.services.contentful import LibraryContentfulClient
from models.marketing import Resource, ResourceTypes
from storage.connection import db


def export_from_contentful():
    client = LibraryContentfulClient(preview=False, user_facing=False)
    skip = 0
    entries = client._client.entries(
        {
            "content_type": "article",
            "locale": "en-US",
            "include": 0,
        }
    )
    all_articles = entries.items
    while (skip := skip + entries.limit) < entries.total:
        entries = client._client.entries(
            {"content_type": "article", "locale": "en-US", "include": 0, "skip": skip}
        )
        all_articles += entries.items

    for article in all_articles:
        if any(
            article.slug.endswith(suffix)
            for suffix in [
                "hi-IN",
                "fr-FR",
                "ja-JP",
                "es-419",
                "it-IT",
                "pl-PL",
                "zh-Hans",
                "pt-BR",
            ]
        ):
            continue

        insert = mysql.insert(Resource, bind=db.engine).values(
            Resource(
                resource_type=ResourceTypes.ENTERPRISE,
                content_type="article",
                contentful_status=ContentfulMigrationStatus.LIVE,
                published_at=datetime.utcnow(),
                title=article.title,
                slug=article.slug,
            ).to_dict()
        )
        insert = insert.on_duplicate_key_update(
            Resource(
                resource_type=ResourceTypes.ENTERPRISE,
                content_type="article",
                contentful_status=ContentfulMigrationStatus.LIVE,
                title=article.title,
                slug=article.slug,
                modified_at=datetime.utcnow(),
            ).to_dict()
        )
        db.session.execute(insert)

    db.session.commit()


if __name__ == "__main__":
    with create_app().app_context():
        export_from_contentful()
