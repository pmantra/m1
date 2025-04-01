"""Add new models for tracks refactor

Revision ID: 5ee926ea8919
Revises: 1e12ae4f52e1
Create Date: 2020-08-10 21:50:42.143534

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5ee926ea8919"
down_revision = "1e12ae4f52e1"
branch_labels = None
depends_on = None


class TrackName(enum.Enum):
    ADOPTION = "adoption"
    BREAST_MILK_SHIPPING = "breast_milk_shipping"
    EGG_FREEZING = "egg_freezing"
    FERTILITY = "fertility"
    GENERIC = "generic"
    PARTNER_FERTILITY = "partner_fertility"
    PARTNER_NEWPARENT = "partner_newparent"
    PARTNER_PREGNANT = "partner_pregnant"
    POSTPARTUM = "postpartum"
    PREGNANCY = "pregnancy"
    PREGNANCYLOSS = "pregnancyloss"
    SPONSORED = "sponsored"
    SURROGACY = "surrogacy"
    PEDIATRICS = "pediatrics"
    TRYING_TO_CONCEIVE = "trying_to_conceive"
    GENERAL_WELLNESS = "general_wellness"
    PARENTING_AND_PEDIATRICS = "parenting_and_pediatrics"


class ExtensionLogic(enum.Enum):
    ALL = "all"
    NON_US = "non_us"


def upgrade():
    _create_track_extension()
    _create_client_track()
    _create_member_track()
    _create_member_track_phase()


def downgrade():
    op.drop_table("member_track_phase")
    op.drop_table("member_track")
    op.drop_table("client_track")
    op.drop_table("track_extension")


def _create_member_track():
    op.create_table(
        "member_track",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "client_track_id",
            sa.Integer,
            sa.ForeignKey("client_track.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "organization_employee_id",
            sa.Integer,
            sa.ForeignKey("organization_employee.id"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean, default=True, nullable=False),
        sa.Column("auto_transitioned", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def _create_member_track_phase():
    op.create_table(
        "member_track_phase",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "member_track_id",
            sa.Integer,
            sa.ForeignKey("member_track.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def _create_client_track():
    op.create_table(
        "client_track",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("track", sa.Enum(TrackName), nullable=False),
        sa.Column("extension_id", sa.Integer, sa.ForeignKey("track_extension.id")),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def _create_track_extension():
    op.create_table(
        "track_extension",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("extension_logic", sa.Enum(ExtensionLogic), nullable=False),
        sa.Column("extension_days", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )
