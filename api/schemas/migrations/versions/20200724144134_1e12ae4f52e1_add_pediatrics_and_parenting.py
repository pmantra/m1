"""Add pediatrics and parenting

Revision ID: 1e12ae4f52e1
Revises: b33161d7bc55
Create Date: 2020-07-24 14:41:34.015731

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1e12ae4f52e1"
down_revision = "b33161d7bc55"
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
    PARENTING_AND_PEDIATRICS_ONBOARDING = "PARENTING_AND_PEDIATRICS_ONBOARDING"
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
    types.remove(NeedsAssessmentTypes.PARENTING_AND_PEDIATRICS_ONBOARDING.value)
    sql = sa.text(
        "ALTER TABLE assessment_lifecycle MODIFY COLUMN type ENUM :types NOT NULL"
    ).bindparams(types=types)
    op.execute(sql)
