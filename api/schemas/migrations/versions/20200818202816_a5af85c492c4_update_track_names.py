"""Update track names

This migration gets rid of an extra enum value, PEDIATRICS. This was redundant
because we have both PEDIATRICS and PARENTING_AND_PEDIATRICS.

Revision ID: a5af85c492c4
Revises: 5ee926ea8919
Create Date: 2020-08-18 20:28:16.212058

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a5af85c492c4"
down_revision = "5ee926ea8919"
branch_labels = None
depends_on = None


class OldTrackName(enum.Enum):
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


class NewTrackName(str, enum.Enum):
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
    TRYING_TO_CONCEIVE = "trying_to_conceive"
    GENERAL_WELLNESS = "general_wellness"
    PARENTING_AND_PEDIATRICS = "parenting_and_pediatrics"


def upgrade():
    op.alter_column(
        "client_track",
        "track",
        existing_type=sa.Enum(OldTrackName),
        type_=sa.Enum(NewTrackName),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "client_track",
        "track",
        existing_type=sa.Enum(NewTrackName),
        type_=sa.Enum(OldTrackName),
        existing_nullable=False,
    )
