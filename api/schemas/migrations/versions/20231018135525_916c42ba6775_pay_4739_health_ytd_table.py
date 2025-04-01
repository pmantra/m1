"""PAY-4739-health-ytd-table

Revision ID: 916c42ba6775
Revises: 3bceec2cb287
Create Date: 2023-10-18 13:55:25.296571+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "916c42ba6775"
down_revision = "3bceec2cb287"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `health_plan_year_to_date_spend` (
            `id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `policy_id` varchar(50) NOT NULL,
            `year` int NOT NULL,
            `organization_id` int NOT NULL,
            `plan_type` enum('INDIVIDUAL', 'FAMILY') default 'INDIVIDUAL',
            `rx_ind_ytd_deductible` int default 0,
            `rx_ind_fam_deductible` int default 0,
            `rx_fam_ytd_oop` int default 0,
            `rx_ind_ytd_oop` int default 0,
            KEY (policy_id),
            FOREIGN KEY (organization_id) REFERENCES organization(`id`)
            );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `health_plan_year_to_date_spend` CASCADE ;
        """
    )
