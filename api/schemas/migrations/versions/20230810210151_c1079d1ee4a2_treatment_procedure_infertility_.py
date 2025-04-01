"""treatment_procedure_infertility_diagnosis_start_date_nullable

Revision ID: c1079d1ee4a2
Revises: 7575498b9710
Create Date: 2023-08-10 21:01:51.998498+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.constants import PatientInfertilityDiagnosis


# revision identifiers, used by Alembic.
revision = "c1079d1ee4a2"
down_revision = "5c0b8c5900fa"
branch_labels = None
depends_on = None


def upgrade():
    diagnoses = [diagnosis.value for diagnosis in PatientInfertilityDiagnosis]
    sql = sa.text(
        "ALTER TABLE `treatment_procedure` "
        "MODIFY COLUMN `infertility_diagnosis` ENUM :diagnoses NULL,"
        "ALGORITHM=INPLACE, LOCK=NONE;"
    ).bindparams(diagnoses=diagnoses)
    op.execute(sql)


def downgrade():
    diagnoses = [diagnosis.value for diagnosis in PatientInfertilityDiagnosis]
    sql = sa.text(
        "ALTER TABLE `treatment_procedure` "
        "MODIFY COLUMN `infertility_diagnosis` ENUM :diagnoses NOT NULL,"
        "ALGORITHM=COPY, LOCK=SHARED;"
    ).bindparams(diagnoses=diagnoses)
    op.execute(sql)
