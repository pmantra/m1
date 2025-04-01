"""Backfill track extensions

Revision ID: d13386699d19
Revises: 3eae69ae3a60
Create Date: 2020-09-08 19:01:40.025289

"""
# from models.enterprise import OrganizationModuleExtension
# from models.tracks.client_track import TrackExtension
# from storage.connection import db


# revision identifiers, used by Alembic.
revision = "d13386699d19"
down_revision = "3eae69ae3a60"
branch_labels = None
depends_on = None

# NOTE: The TrackExtension model has been removed from the codebase
# and this migration can no longer be run.


def upgrade():
    pass
    # extensions = (
    #     OrganizationModuleExtension.query.with_entities(
    #         OrganizationModuleExtension.extension_logic,
    #         OrganizationModuleExtension.extension_days,
    #     )
    #     .distinct()
    #     .all()
    # )

    # for old_extension in extensions:
    #     track_extension = TrackExtension(
    #         extension_logic=old_extension.extension_logic.value.lower(),
    #         extension_days=old_extension.extension_days,
    #     )
    #     db.session.add(track_extension)

    # db.session.commit()


def downgrade():
    pass
    # TrackExtension.query.delete()
    # db.session.commit()
