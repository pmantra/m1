"""Add referral Assessment Lifecycle Types

Revision ID: a34c8ce5944c
Revises: 2608bcf9379b
Create Date: 2021-07-08 20:42:23.208112+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a34c8ce5944c"
down_revision = "2608bcf9379b"
branch_labels = None
depends_on = None


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
    PARTNER_FERTILITY_ONBOARDING = "PARTNER_FERTILITY_ONBOARDING"
    PARTNER_PREGNANCY_ONBOARDING = "PARTNER_PREGNANCY_ONBOARDING"
    PARTNER_NEWPARENT_ONBOARDING = "PARTNER_NEWPARENT_ONBOARDING"
    M_QUIZ = "M_QUIZ"
    E_QUIZ = "E_QUIZ"
    C_QUIZ = "C_QUIZ"
    REFERRAL_REQUEST = "REFERRAL_REQUEST"
    REFERRAL_FEEDBACK = "REFERRAL_FEEDBACK"


def upgrade():
    types = [type.value for type in NeedsAssessmentTypes]
    sql = sa.text(
        "ALTER TABLE assessment_lifecycle MODIFY COLUMN type ENUM :types NOT NULL"
    ).bindparams(types=types)
    op.execute(sql)


def downgrade():
    types = [type.value for type in NeedsAssessmentTypes]
    types.remove(NeedsAssessmentTypes.REFERRAL_REQUEST.value)
    types.remove(NeedsAssessmentTypes.REFERRAL_FEEDBACK.value)
    sql = sa.text(
        "ALTER TABLE assessment_lifecycle MODIFY COLUMN type ENUM :types NOT NULL"
    ).bindparams(types=types)
    op.execute(sql)
