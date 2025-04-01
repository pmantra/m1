import datetime
import json

import contentful

from models.enterprise import (  # type: ignore[attr-defined] # Module "models.enterprise" has no attribute "OrganizationContentResource"
    OrganizationContentResource,
)
from models.marketing import Resource, ResourceTypes
from storage.connection import db
from views.content import (  # type: ignore[attr-defined] # Module "views.content" has no attribute "CONTENTFUL_API_KEY" #type: ignore[attr-defined] # Module "views.content" has no attribute "CONTENTFUL_SPACE_ID" #type: ignore[attr-defined] # Module "views.content" has no attribute "CONTENTFUL_PRIVATE_SPACE_ID" #type: ignore[attr-defined] # Module "views.content" has no attribute "CONTENTFUL_PRIVATE_API_KEY"
    CONTENTFUL_API_KEY,
    CONTENTFUL_PRIVATE_API_KEY,
    CONTENTFUL_PRIVATE_SPACE_ID,
    CONTENTFUL_SPACE_ID,
)


def backfill_resources():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    client = contentful.Client(CONTENTFUL_SPACE_ID, CONTENTFUL_API_KEY)
    private_client = contentful.Client(
        CONTENTFUL_PRIVATE_SPACE_ID, CONTENTFUL_PRIVATE_API_KEY
    )

    print("backfilling resources...")
    resource_errors = _backfill_resources(client, ResourceTypes.ENTERPRISE)
    print("backfilling private resources...")
    private_resource_errors = _backfill_resources(private_client, ResourceTypes.PRIVATE)

    if resource_errors:
        print(
            f"Error(s) backfilling resources: \n{json.dumps(resource_errors, indent=2)}"
        )
    if private_resource_errors:
        print(
            "Error(s) backfilling private resources: \n{}".format(
                json.dumps(private_resource_errors, indent=2)
            )
        )


def _backfill_resources(client, resource_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    errors = []
    for entry in client.entries({"limit": 1000}):
        try:
            _create_resource(entry, resource_type)
        except Exception as e:
            print("Error creating resource...")
            db.session.rollback()
            errors.append({"entry_id": entry.id, "error": str(e)})
    return errors


def _create_resource(entry, resource_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    print(f"backfilling entry: {entry}")
    if not hasattr(entry, "title"):
        print("Empty entry, skipping...")
        return
    resource = Resource(
        legacy_id=entry.id,
        resource_type=resource_type,
        published_at=datetime.datetime.utcnow(),
        body=entry.body,
        title=entry.title,
        slug=_check_slug(entry.url_slug),
    )
    db.session.add(resource)
    for org_content_resource in (
        db.session.query(OrganizationContentResource)
        .filter(OrganizationContentResource.content_id == entry.id)
        .all()
    ):
        resource.allowed_modules.append(org_content_resource.module)
        resource.allowed_organizations.append(org_content_resource.organization)
    db.session.commit()


def _check_slug(slug):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    existing = db.session.query(Resource).filter(Resource.slug.startswith(slug)).all()
    if existing:
        return f"{slug}-{len(existing)}"
    return slug
