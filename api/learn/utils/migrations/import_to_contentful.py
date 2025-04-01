"""
import_to_contentful.py

Takes a file consisting of a JSON object with string resource ids as keys and
Contentful entry representations as values, and uploads them to Contentful.

Usage:
    import_to_contentful.py (--filename=<filename>)

Options:
  --filename=<filename>         Provide a filename under the utils/migrations/webflow folder to read from
"""
import copy
import hashlib
import json

import contentful_management
import docopt

from app import create_app
from learn.models import migration
from learn.utils.migrations import constants
from models import marketing
from storage.connection import db
from utils.log import logger

log = logger(__name__)

client = contentful_management.Client(constants.CONTENTFUL_MANAGEMENT_KEY)
environment = client.environments(constants.CONTENTFUL_SPACE_ID).find(
    constants.CONTENTFUL_ENVIRONMENT_ID
)


def import_to_contentful(filename):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with open(f"learn/utils/migrations/{filename}") as f:
        resources = json.load(f)
    for string_id, entry_obj in resources.items():
        try:
            # Remove related reads for now, it's just a list of slugs and not
            # in the correct format yet.  We'll handle later in the script
            entry_obj = copy.deepcopy(entry_obj)
            entry_obj["fields"]["relatedReads"]["en-US"] = []

            slug = entry_obj["fields"]["slug"]["en-US"]

            # Earlier, we replaced line breaks in list items with a magic string,
            # since markdown doesn't handle them well.  Now turning them back
            entry_obj_str = json.dumps(entry_obj)
            entry_obj_str = entry_obj_str.replace(
                constants.LINE_BREAK_REPLACEMENT_STRING, "\n"
            )
            # strict=False is to keep it from getting mad about the \ns
            entry_obj = json.loads(entry_obj_str, strict=False)

            # Now change back to a string for ease of replacing other magic strings
            entry_obj_str = json.dumps(entry_obj)

            # Create all embedded entry stuff now
            accordions = entry_obj["embedded_entries"].get("accordions", [])
            entry_obj_str = handle_accordions_and_return_str(
                accordions=accordions,
                slug=slug,
                entry_obj_str=entry_obj_str,
            )

            callouts = entry_obj["embedded_entries"].get("callouts", [])
            entry_obj_str = handle_callouts_and_return_str(
                callouts=callouts,
                slug=slug,
                entry_obj_str=entry_obj_str,
            )

            embedded_images = entry_obj["embedded_entries"].get("embedded_images", [])
            entry_obj_str = handle_embedded_images_and_return_str(
                embedded_images=embedded_images,
                slug=slug,
                entry_obj_str=entry_obj_str,
            )

            # strict=False is to keep it from getting mad about the \ns
            entry_obj = json.loads(entry_obj_str, strict=False)

            entry_id = hashlib.md5(slug.encode()).hexdigest()
            entry = create_or_update_entry(
                entry_id=entry_id, entry_obj=entry_obj, slug=slug
            )
            entry.publish()

            resource = db.session.query(marketing.Resource).get(int(string_id))
            if (
                resource.contentful_status
                == migration.ContentfulMigrationStatus.NOT_STARTED
            ):
                resource.contentful_status = (
                    migration.ContentfulMigrationStatus.IN_PROGRESS
                )
            # Commit even if status didn't change to prevent "Lost connection
            # to MySQL server during query" error
            db.session.commit()
        except Exception as e:
            log.error(
                "Error creating or updating Contentful entry for resource",
                slug=slug,
                error=e,
            )
            db.session.rollback()


def handle_accordions_and_return_str(accordions: list, slug: str, entry_obj_str: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for accordion in accordions:
        # Create all accordion items
        item_ids = []
        for item in accordion["items"]:
            item_entry_dict = {
                "content_type_id": "accordionItem",
                "fields": {
                    "header": {"en-US": item["header"]},
                    "body": {"en-US": item["rich_text"]},
                },
            }
            item_id = hashlib.md5(json.dumps(item["rich_text"]).encode()).hexdigest()
            log.info("Creating/updating accordion item")
            item_entry = create_or_update_entry(
                entry_id=item_id, entry_obj=item_entry_dict, slug=slug
            )
            item_entry.publish()
            item_ids.append(item_id)
        accordion_entry_dict = {
            "content_type_id": "accordion",
            "fields": {
                "name": {"en-US": accordion["name"]},
                "headingLevel": {"en-US": accordion["heading_level"]},
                "items": {
                    "en-US": [contentful_link_dict(item_id) for item_id in item_ids]
                },
            },
        }
        accordion_entry = create_or_update_entry(
            entry_id=accordion["id"], entry_obj=accordion_entry_dict, slug=slug
        )
        accordion_entry.publish()
        log.info("Created accordion entry", slug=slug, entry_id=accordion["id"])

        # Replace accordion magic strings in the main article rich text with link objects
        accordion_id = accordion.pop("id")
        entry_obj_str = replace_fake_h1s_with_link_objs(
            entry_id=accordion_id,
            entry_obj_str=entry_obj_str,
            magic_str=constants.ACCORDION_REPLACEMENT_STRING,
        )
    return entry_obj_str


def handle_callouts_and_return_str(callouts: list, slug: str, entry_obj_str: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for callout in callouts:
        callout_entry_dict = {
            "content_type_id": "callout",
            # Why did I name this richText and the accordion one body. why
            "fields": {
                "name": {"en-US": callout["name"]},
                "richText": {"en-US": callout["body"]},
            },
        }
        callout_id = hashlib.md5(json.dumps(callout["body"]).encode()).hexdigest()
        log.info("Creating/updating callout")
        callout_entry = create_or_update_entry(
            entry_id=callout_id, entry_obj=callout_entry_dict, slug=slug
        )
        callout_entry.publish()

        entry_obj_str = replace_fake_h1s_with_link_objs(
            entry_id=callout_id,
            entry_obj_str=entry_obj_str,
            magic_str=constants.CALLOUT_REPLACEMENT_STRING,
        )
    return entry_obj_str


def handle_embedded_images_and_return_str(
    embedded_images: list, slug: str, entry_obj_str: str
) -> str:
    for embedded_image in embedded_images:
        asset_id = embedded_image["asset_id"]
        if embedded_image["caption"]:
            caption = embedded_image["caption"]
            img_entry_dict = {
                "content_type_id": "embeddedImage",
                "fields": {
                    "image": {
                        "en-US": {
                            "sys": {
                                "type": "Link",
                                "linkType": "Asset",
                                "id": asset_id,
                            },
                        }
                    },
                    "caption": {"en-US": caption},
                },
            }
            entry_id = hashlib.md5(
                (asset_id + json.dumps(caption)).encode()
            ).hexdigest()
            log.info("Creating/updating embedded image")
            img_entry = create_or_update_entry(
                entry_id=entry_id, entry_obj=img_entry_dict, slug=slug
            )
            img_entry.publish()

            entry_obj_str = replace_fake_h1s_with_link_objs(
                entry_id=entry_id,
                entry_obj_str=entry_obj_str,
                magic_str=constants.IMG_W_CAPTION_REPLACEMENT_STRING,
            )
        else:
            embedded_rich_text = {
                "nodeType": "embedded-asset-block",
                "data": {
                    "target": {
                        "sys": {
                            "type": "Link",
                            "linkType": "Asset",
                            "id": asset_id,
                        },
                    },
                },
                "content": [],
            }
            entry_obj_str = entry_obj_str.replace(
                '{"nodeType": "heading-1", "content": [{"nodeType": "text", "value": "'
                + constants.IMG_REPLACEMENT_STRING
                + '", "marks": [], "data": {}}], "data": {}}',
                json.dumps(embedded_rich_text),
                # Replace one occurrence of the string at a time
                1,
            )
    return entry_obj_str


def replace_fake_h1s_with_link_objs(entry_id: str, entry_obj_str: str, magic_str: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    embedded_rich_text = {
        "nodeType": "embedded-entry-block",
        "data": {
            "target": contentful_link_dict(entry_id),
        },
        "content": [],
    }
    # Probably highly dependent on JSON formatting but whatever it works
    # Replace fake h1s with the accordions whose place they are holding
    entry_obj_str = entry_obj_str.replace(
        '{"nodeType": "heading-1", "content": [{"nodeType": "text", "value": "'
        + magic_str
        + '", "marks": [], "data": {}}], "data": {}}',
        json.dumps(embedded_rich_text),
        # Replace one occurrence of the string at a time
        1,
    )
    return entry_obj_str


def create_or_update_entry(entry_id: str, entry_obj: dict, slug: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if entry := contentful_entry_or_none(entry_id):
        # User id of System User 😩 to avoid overwriting updates made by not us
        if entry.sys["updated_by"].id == "68Dt5BFcqcyZ6Euy85whgj":
            entry.update(entry_obj)
            log.info("Updated contentful entry", slug=slug, entry_id=entry_id)
        else:
            log.info(
                "Contentful entry has already been updated by someone else; not updating",
                slug=slug,
                entry_id=entry_id,
            )
    else:
        entry = environment.entries().create(entry_id, entry_obj)
        log.info("Created contentful entry", slug=slug, entry_id=entry_id)
    return entry


def contentful_entry_or_none(entry_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        return environment.entries().find(entry_id)
    except contentful_management.errors.NotFoundError:
        log.debug("No Contentful entry found", entry_id=entry_id)
    except Exception as e:
        log.error("Error retrieving Contentful entry", entry_id=entry_id, error=e)
        raise e


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
        import_to_contentful(args["--filename"])
