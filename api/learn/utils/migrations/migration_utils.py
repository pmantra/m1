from os import environ
from typing import Any, Dict, Optional

from contentful_management import Client, Entry
from contentful_management.environment import Environment

LEARN_SPACE_ID = environ["CONTENTFUL_LEARN_SPACE_ID"]


def get_environment(
    client: Client, environment_id: str, space_id: Optional[str] = LEARN_SPACE_ID
) -> Environment:
    return client.spaces().find(space_id).environments().find(environment_id)


def get_entry_by_slug(
    environment: Environment, content_type: str, slug: str
) -> Optional[Entry]:
    return next(
        iter(
            environment.entries().all(
                query={
                    "content_type": content_type,
                    "fields.slug": slug,
                }
            )
        ),
        None,
    )


def create_entry(
    environment: Environment,
    id_: str,
    content_type: str,
    fields: Dict[str, Any],
    publish: bool = False,
) -> Entry:
    entry = environment.entries().create(
        id_, {"content_type_id": content_type, "fields": fields}
    )
    if publish:
        entry.publish()
    return entry
