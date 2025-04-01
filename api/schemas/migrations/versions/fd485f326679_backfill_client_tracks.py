"""Backfill client tracks

Revision ID: fd485f326679
Revises: 06e560ec6777
Create Date: 2020-09-11 18:07:58.942253

"""
# import sqlalchemy as sa

# from models.programs import Module
# from models.tracks.client_track import ClientTrack, TrackExtension
# from storage.connection import db
# from models.enterprise import Organization, OrganizationModuleExtension


# revision identifiers, used by Alembic.
revision = "fd485f326679"
down_revision = "06e560ec6777"
branch_labels = None
depends_on = None

# NOTE: The TrackExtension model has been removed from the codebase
# and this migration can no longer be run.


def upgrade():
    pass
    # track_extensions = db.session.query(
    #     TrackExtension.id,
    #     TrackExtension.extension_logic.label("logic"),
    #     TrackExtension.extension_days.label("days"),
    # ).all()
    # track_extension_ids = {
    #     f"{extension.logic}{extension.days}": extension.id
    #     for extension in track_extensions
    # }

    # org_module_extension_combos = _get_all_org_module_extension_combinations()
    # for combo in org_module_extension_combos:
    #     client_track = ClientTrack(
    #         track=combo.module_name,
    #         extension_id=track_extension_ids.get(
    #             f"{combo.logic.value.lower() if combo.logic else None}{combo.days}"
    #         ),
    #         organization_id=combo.organization_id,
    #     )
    #     db.session.add(client_track)

    # db.session.commit()


def downgrade():
    pass


#     ClientTrack.query.delete()
#     db.session.commit()


# def _get_all_org_module_extension_combinations():
#     return (
#         db.session.query(
#             Organization.id.label("organization_id"),
#             Module.name.label("module_name"),
#             OrganizationModuleExtension.extension_logic.label("logic"),
#             OrganizationModuleExtension.extension_days.label("days"),
#         )
#         .join(Organization.allowed_modules)
#         .outerjoin(
#             OrganizationModuleExtension,
#             sa.and_(
#                 OrganizationModuleExtension.organization_id == Organization.id,
#                 OrganizationModuleExtension.module_id == Module.id,
#             ),
#         )
#         .order_by(Organization.id, Module.id)
#         .all()
#     )
