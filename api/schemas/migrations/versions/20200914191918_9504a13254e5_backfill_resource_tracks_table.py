"""Backfill resource_tracks table from resource_modules

Revision ID: 9504a13254e5
Revises: 06c9041e0839
Create Date: 2020-09-14 19:19:18.714293

"""
from models.marketing import Resource, resource_modules, ResourceTrack
from models.programs import Module

from storage.connection import db

# revision identifiers, used by Alembic.
revision = "9504a13254e5"
down_revision = "06c9041e0839"
branch_labels = None
depends_on = None


def upgrade():
    # gets (resource_id, module_name) tuples
    resources_with_modules = (
        db.session.query(
            Resource.id.label("resource_id"), Module.name.label("track_name")
        )
        .join(resource_modules, Resource.id == resource_modules.c.resource_id)
        .join(Module, resource_modules.c.module_id == Module.id)
        .all()
    )
    if resources_with_modules:
        db.session.bulk_insert_mappings(
            ResourceTrack, [row._asdict() for row in resources_with_modules]
        )
        db.session.commit()


def downgrade():
    ResourceTrack.query.delete()
    db.session.commit()
