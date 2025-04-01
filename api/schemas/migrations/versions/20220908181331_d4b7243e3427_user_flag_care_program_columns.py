"""user_flag_care_program_columns

Revision ID: d4b7243e3427
Revises: 115645387a0f
Create Date: 2022-09-08 18:13:31.250760+00:00

"""

import enum
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4b7243e3427"
down_revision = "115645387a0f"
branch_labels = None
depends_on = None


def upgrade():

    # enums used by Care Programs in the CPS service
    class ECPFlagTypes(enum.Enum):
        RISK = "RISK"
        CONDITION = "CONDITION"

    class ECPProgramQualifiers(enum.Enum):
        MENTAL_HEALTH = "MENTAL_HEALTH"
        CHRONIC_CONDITIONS = "CHRONIC_CONDITIONS"

    op.add_column(
        "user_flag", sa.Column("ecp_flag_type", sa.Enum(ECPFlagTypes), nullable=True)
    )
    op.add_column(
        "user_flag",
        sa.Column(
            "ecp_program_qualifier", sa.Enum(ECPProgramQualifiers), nullable=True
        ),
    )


def downgrade():
    op.drop_column("user_flag", "ecp_flag_type")
    op.drop_column("user_flag", "ecp_program_qualifier")
