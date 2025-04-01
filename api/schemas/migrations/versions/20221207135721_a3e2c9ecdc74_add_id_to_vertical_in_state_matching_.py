"""add_id_to_vertical_in_state_matching_table

Revision ID: a3e2c9ecdc74
Revises: 90b41a57e73f
Create Date: 2022-12-07 13:57:21.066687+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a3e2c9ecdc74"
down_revision = "90b41a57e73f"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("vertical_in_state_matching")

    op.execute(
        """
    CREATE TABLE `vertical_in_state_matching` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `vertical_id` int(11) NOT NULL,
        `subdivision_code` varchar(6) NOT NULL,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uq_vertical_subdivision` (`vertical_id`, `subdivision_code`),
        CONSTRAINT `vertical_subdivision_ibfk_1` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`)
    )
    """
    )


def downgrade():
    op.drop_table("vertical_in_state_matching")

    op.execute(
        """
    CREATE TABLE `vertical_in_state_matching` (
        `vertical_id` int(11) NOT NULL,
        `subdivision_code` varchar(6) NOT NULL,
        PRIMARY KEY (`vertical_id`,`subdivision_code`),
        CONSTRAINT `vertical_in_state_matching_ibfk_1` FOREIGN KEY (`vertical_id`) REFERENCES `vertical` (`id`)
    )
    """
    )
