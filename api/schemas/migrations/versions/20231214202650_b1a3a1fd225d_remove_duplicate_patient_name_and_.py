"""remove_duplicate_patient_name_and_nullable

Revision ID: b1a3a1fd225d
Revises: d5043f590cba
Create Date: 2023-12-14 20:26:50.491879+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b1a3a1fd225d"
down_revision = "d5043f590cba"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        DROP COLUMN `member_date_of_birth`;
        
        ALTER TABLE `employer_health_plan`
        CHANGE COLUMN `ind_deductible_limit` `ind_deductible_limit` int(11) DEFAULT NULL,
        CHANGE COLUMN `fam_deductible_limit` `fam_deductible_limit` int(11) DEFAULT NULL,
        CHANGE COLUMN `ind_oop_max_limit` `ind_oop_max_limit` int(11) DEFAULT NULL,
        CHANGE COLUMN `fam_oop_max_limit` `fam_oop_max_limit` int(11) DEFAULT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        ADD COLUMN `member_date_of_birth` date DEFAULT NULL;
        
        ALTER TABLE `employer_health_plan`
        CHANGE COLUMN `ind_deductible_limit` `ind_deductible_limit` int(11) NOT NULL,
        CHANGE COLUMN `fam_deductible_limit` `fam_deductible_limit` int(11) NOT NULL,
        CHANGE COLUMN `ind_oop_max_limit` `ind_oop_max_limit` int(11) NOT NULL,
        CHANGE COLUMN `fam_oop_max_limit` `fam_oop_max_limit` int(11) NOT NULL;
        """
    )
