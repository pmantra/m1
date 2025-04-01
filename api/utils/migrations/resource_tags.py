import csv
import os

from slugify import slugify

from models.marketing import Resource, ResourceContentTypes, Tag
from models.programs import Module
from storage.connection import db

CSV_FILE_PATH = f"{os.path.dirname(os.path.realpath(__file__))}/resource_tags.csv"
RESOURCE_CONTENT_TYPE_NAMES = {rt.name for rt in ResourceContentTypes}


def import_resource_tags():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with open(CSV_FILE_PATH) as fp:
        reader = csv.DictReader(fp)
        errors = []
        for row in reader:
            error = _update_resource(**row)
            if error:
                errors.append(error)
    if errors:
        print(f"Errors importing resource tags: {errors}")


def _update_resource(resource_id, module_name, resource_type, tag_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    resource = db.session.query(Resource).get(resource_id)
    if not resource:
        return f"Resource {resource_id} not found!"

    module = db.session.query(Module).filter(Module.name == module_name).one_or_none()
    if module is None:
        return f"Module name: {module_name} not found"

    if resource_type not in RESOURCE_CONTENT_TYPE_NAMES:
        return f"Invalid resource type name: {resource_type}"

    if tag_name:
        internal_tag_name = slugify(tag_name.replace("&", "and"), separator="_")
        tag = db.session.query(Tag).filter(Tag.name == internal_tag_name).one_or_none()
        if not tag:
            tag = Tag(display_name=tag_name, name=internal_tag_name)
            db.session.add(tag)
        resource.tags.append(tag)

    resource.allowed_modules.append(module)
    resource.content_type = resource_type
    db.session.commit()
