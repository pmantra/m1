"""Add Maven Planning assessment types

Revision ID: b3845cc40284
Revises: d6ab6a15e955
Create Date: 2020-06-12 21:38:17.707110

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3845cc40284"
down_revision = "d6ab6a15e955"
branch_labels = None
depends_on = None


# Copied from models.enterprise
class NeedsAssessmentTypes(enum.Enum):
    PREGNANCY = "PREGNANCY"  # notes for intro appt
    POSTPARTUM = "POSTPARTUM"  # notes for intro appt
    # onboarding NAs are filled out at signup and used to match for care team
    PREGNANCY_ONBOARDING = "PREGNANCY_ONBOARDING"
    POSTPARTUM_ONBOARDING = "POSTPARTUM_ONBOARDING"
    EGG_FREEZING_ONBOARDING = "EGG_FREEZING_ONBOARDING"
    FERTILITY_ONBOARDING = "FERTILITY_ONBOARDING"
    PREGNANCYLOSS_ONBOARDING = "PREGNANCYLOSS_ONBOARDING"
    SURROGACY_ONBOARDING = "SURROGACY_ONBOARDING"
    ADOPTION_ONBOARDING = "ADOPTION_ONBOARDING"
    BREAST_MILK_SHIPPING_ONBOARDING = "BREAST_MILK_SHIPPING_ONBOARDING"
    TRYING_TO_CONCEIVE_ONBOARDING = "TRYING_TO_CONCEIVE_ONBOARDING"
    GENERAL_WELLNESS_ONBOARDING = "GENERAL_WELLNESS_ONBOARDING"
    M_QUIZ = "M_QUIZ"
    E_QUIZ = "E_QUIZ"
    C_QUIZ = "C_QUIZ"


def upgrade():
    types = [type.value for type in NeedsAssessmentTypes]
    sql = sa.text(
        "ALTER TABLE assessment_lifecycle MODIFY COLUMN type ENUM :types NOT NULL"
    ).bindparams(types=types)
    op.execute(sql)


def downgrade():
    types = [type.value for type in NeedsAssessmentTypes]
    types.remove(NeedsAssessmentTypes.TRYING_TO_CONCEIVE_ONBOARDING.value)
    types.remove(NeedsAssessmentTypes.GENERAL_WELLNESS_ONBOARDING.value)
    sql = sa.text(
        "ALTER TABLE assessment_lifecycle MODIFY COLUMN type ENUM :types NOT NULL"
    ).bindparams(types=types)
    op.execute(sql)
