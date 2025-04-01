"""
remove_resources_that_shouldnt_be_indexed_from_index.py

De-indexes resources that do not meet the criteria for search.
If not run with --force, just prints the names of the resources.

Usage:
    remove_resources_that_shouldnt_be_indexed_from_index.py [--force]

Options:
  --force                       Actually remove the resources from the index
"""
from docopt import docopt
from sqlalchemy import and_, or_

from app import create_app
from models import marketing
from views import search


def remove_em(force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client = search.get_client()
    engine_name = search.get_resources_engine()

    # Remove an admin resource from search if it's an article-ish type and either
    # has no published at, has no allowed tracks, or has no tags
    admin_resources = marketing.Resource.query.filter(
        marketing.Resource.content_type.in_(
            [
                marketing.ResourceContentTypes.article.name,
                marketing.ResourceContentTypes.real_talk.name,
                marketing.ResourceContentTypes.ask_a_practitioner.name,
            ]
        ),
        marketing.Resource.webflow_url == None,
        or_(
            marketing.Resource.published_at == None,
            marketing.Resource.allowed_tracks == None,
            marketing.Resource.tags == None,
        ),
    )

    admin_resources_to_remove = []
    for resource in admin_resources:
        res = client.get_documents(
            engine_name=engine_name, document_ids=[f"resource:{resource.id}"]
        )
        # Response will come back as an array with one thing in it
        # If the document was not found, that thing will be a `None`
        if res and res[0]:
            admin_resources_to_remove.append(resource)

    # Remove a webflow resource from search if it's an article-ish type and either
    # has no published at OR has neither tracks nor tags nor phases
    webflow_resources = marketing.Resource.query.filter(
        marketing.Resource.content_type.in_(
            [
                marketing.ResourceContentTypes.article.name,
                marketing.ResourceContentTypes.real_talk.name,
                marketing.ResourceContentTypes.ask_a_practitioner.name,
            ]
        ),
        marketing.Resource.webflow_url != None,
        or_(
            marketing.Resource.published_at == None,
            and_(
                (marketing.Resource.allowed_tracks == None),
                (marketing.Resource.tags == None),
                (marketing.Resource.allowed_track_phases == None),
            ),
        ),
    )

    webflow_resources_to_remove = []
    for resource in webflow_resources:
        res = client.get_documents(
            engine_name=engine_name, document_ids=[f"resource:{resource.id}"]
        )
        if res and res[0]:
            webflow_resources_to_remove.append(resource)

    print(f"Admin resources: {[r.title for r in admin_resources_to_remove]}")
    print(f"Webflow resources: {[r.title for r in webflow_resources_to_remove]}")

    if force:
        ids = [
            f"resource:{r.id}"
            for r in (admin_resources_to_remove + webflow_resources_to_remove)
        ]
        client.delete_documents(engine_name=engine_name, document_ids=ids)


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        remove_em(force=args["--force"])
