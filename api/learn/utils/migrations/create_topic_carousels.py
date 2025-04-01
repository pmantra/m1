"""
create_topic_carousels.py

Usage: create_topic_carousels.py --dashboard-environment=<name> --learn-environment=<name> --management-token=<token> --track=<name> --tags=<comma_separated_tags>
"""
from os import environ
from typing import List

import docopt
from contentful_management import Client

from app import create_app
from learn.models.migration import ContentfulMigrationStatus
from learn.utils.migrations.migration_utils import (
    create_entry,
    get_entry_by_slug,
    get_environment,
)
from learn.utils.resource_utils import populate_estimated_read_times_and_media_types
from models.marketing import (
    Resource,
    ResourceContentTypes,
    ResourceTrack,
    ResourceTypes,
    Tag,
)
from storage.connection import db


def create_topic_carousels(
    dashboard_environment_id: str,
    learn_environment_id: str,
    management_token: str,
    track_name: str,
    tag_names: List[str],
):
    client = Client(access_token=management_token, default_locale="en")
    learn_space_id = environ["CONTENTFUL_LEARN_SPACE_ID"]
    dashboard_space_id = "skxj1h7bf8uk"

    dashboard_environment = get_environment(
        client=client,
        environment_id=dashboard_environment_id,
        space_id=dashboard_space_id,
    )
    learn_environment = get_environment(
        client=client, environment_id=learn_environment_id
    )

    track_name_kebab = track_name.replace("_", "-")

    for tag in tag_names:
        print(f"⚙️ Processing track_name {track_name} and tag {tag}...")  # noqa
        content_carousel_cards = []
        tag_from_db = db.session.query(Tag).filter(Tag.name == tag).one_or_none()
        if not tag_from_db:
            print(f"No tag found in DB for {tag}")  # noqa
            continue

        tag_name_kebab = (
            tag_from_db.display_name.lower()
            .replace(",", "")
            .replace("&", "")
            .replace("  ", " ")
            .replace(" ", "-")
        )

        resource_query = (
            db.session.query(Resource)
            .join(Resource.tags)
            .join(ResourceTrack)
            .filter(Resource.resource_type == ResourceTypes.ENTERPRISE.name)
            .filter(Resource.content_type != ResourceContentTypes.on_demand_class.name)
            .filter(Resource.published_at is not None)
            .filter(Resource.contentful_status == ContentfulMigrationStatus.LIVE.name)
            .filter(ResourceTrack.track_name == track_name)
            .filter(Tag.name.in_(tag_names))  # type: ignore[attr-defined]
            .order_by(Resource.published_at.desc())
            .limit(20)
        )

        resources = populate_estimated_read_times_and_media_types(resource_query.all())

        for resource in resources:
            article = get_entry_by_slug(
                environment=learn_environment,
                content_type="article",
                slug=resource.slug,
            )
            if article is None:
                print(  # noqa
                    f"⚠️ Couldn't locate entry with slug {resource.slug} in Contentful, even though `contentful_status` is `LIVE`."
                )
                continue

            content_carousel_card_slug = f"content-carousel-card-{resource.media_type}-{track_name_kebab}-{tag_name_kebab}-{len(content_carousel_cards) + 1}-{resource.slug}"
            content_carousel_card = get_entry_by_slug(
                environment=dashboard_environment,
                content_type="contentCarouselCard",
                slug=content_carousel_card_slug,
            )
            if content_carousel_card:
                print(  # noqa
                    f"🔄 Content carousel card with slug {content_carousel_card_slug} already exists."
                )
            else:
                print(  # noqa
                    f"🆕 Creating content carousel card with slug {content_carousel_card_slug}."
                )
                content_carousel_card = create_entry(
                    environment=dashboard_environment,
                    # ids have a max length of 64 characters
                    id_=f"{f'content-carousel-card-article-{track_name_kebab}-{tag_name_kebab}'[:60]}-{len(content_carousel_cards) + 1}",
                    content_type="contentCarouselCard",
                    fields={
                        "slug": {"en": content_carousel_card_slug},
                        "minimumWeek": {"en": 1},
                        "content": {
                            "en": {
                                "sys": {
                                    "linkType": "Contentful:Entry",
                                    "type": "ResourceLink",
                                    "urn": f"crn:contentful:::content:spaces/{learn_space_id}/environments/{learn_environment_id}/entries/{article.id}",
                                }
                            },
                        },
                    },
                )
            content_carousel_card.publish()
            content_carousel_cards.append(content_carousel_card)

        if content_carousel_cards:
            content_carousel_block_slug = (
                f"{track_name_kebab}-{tag_name_kebab}-content-carousel-block"
            )
            content_carousel_block = get_entry_by_slug(
                environment=dashboard_environment,
                content_type="resourcesHeader",
                slug=content_carousel_block_slug,
            )
            if content_carousel_block:
                print(  # noqa
                    f"🔄 Content carousel block with slug {content_carousel_block_slug} already exists. Updating with cards."
                )
                content_carousel_block.children = content_carousel_cards
                content_carousel_block.save()
            else:
                print(  # noqa
                    f"🆕 Creating content carousel block with slug {content_carousel_block_slug}."
                )
                create_entry(
                    environment=dashboard_environment,
                    # ids have a max length of 64 characters
                    id_=f"{f'{track_name_kebab}-{tag_name_kebab}'[:41]}-content-carousel-block",
                    content_type="resourcesHeader",
                    fields={
                        "slug": {"en": content_carousel_block_slug},
                        "title": {"en": tag_from_db.display_name},
                        "children": {
                            "en": [
                                content_carousel_card.to_link().raw
                                for content_carousel_card in content_carousel_cards
                            ]
                        },
                        "showContentType": {"en": False},
                        "ctaText": {"en": "See all"},
                        "ctaUrl": {"en": f"/app/library/topic/{tag_from_db.name}"},
                    },
                )
            print(  # noqa
                f"✅ Successfully created or updated content carousel block with slug {content_carousel_block_slug}."
            )
        else:
            print(  # noqa
                f"🚫 No valid articles for track_name {track_name} and tag {tag}. No block or cards were created."
            )

    return


if __name__ == "__main__":
    args = docopt.docopt(__doc__)
    with create_app().app_context():
        create_topic_carousels(
            dashboard_environment_id=args["--dashboard-environment"],
            learn_environment_id=args["--learn-environment"],
            management_token=args["--management-token"],
            track_name=args["--track"],
            tag_names=args["--tags"].split(","),
        )
