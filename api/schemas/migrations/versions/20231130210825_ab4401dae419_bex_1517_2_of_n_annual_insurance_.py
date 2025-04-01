"""BEX-1517_2_of_n_annual_insurance_questionnaire_response

Revision ID: ab4401dae419
Revises: 4ac3db519080
Create Date: 2023-11-30 21:08:25.513795+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ab4401dae419"
down_revision = "4ac3db519080"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ALTER TABLE annual_insurance_questionnaire_response
            ADD COLUMN survey_year int(4) not null,
            ADD UNIQUE KEY uk_wallet_id_survey_year(wallet_id, survey_year),
            ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """ALTER TABLE annual_insurance_questionnaire_response
            DROP COLUMN survey_year,
            DROP KEY uk_wallet_id_survey_year,
            ALGORITHM=INPLACE, LOCK=NONE
        """
    )
