"""Create table and columns for track change reasons

Revision ID: 89c048ca2842
Revises: 3130938c18af
Create Date: 2022-08-11 16:06:51.978243+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "89c048ca2842"
down_revision = "b20d9e87e778"
branch_labels = None
depends_on = None


def upgrade():

    op.execute(
        """
        CREATE TABLE `track_change_reason` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `name` varchar(120) NOT NULL,
        `display_name` varchar(120) NOT NULL,
        `description` varchar(255) DEFAULT NULL,
        PRIMARY KEY(`id`),
        UNIQUE KEY `name`(`name`),
        UNIQUE KEY `display_name`(`display_name`)
        );
        """
    )
    op.execute(
        """
        ALTER TABLE `member_track` 
        ADD COLUMN `closure_reason_id` int(11) DEFAULT NULL,
        ADD CONSTRAINT `member_track_closure_reason_id_fk` FOREIGN KEY (`closure_reason_id`) REFERENCES `track_change_reason` (`id`),
        LOCK = SHARED;
        """
    )  # LOCK = SHARED; (permit reads)


def downgrade():
    op.execute(
        """        
        ALTER TABLE `member_track`
        DROP FOREIGN KEY `member_track_closure_reason_id_fk`;
        """
    )
    op.execute(
        """        
        ALTER TABLE `member_track`
        DROP COLUMN `closure_reason_id`;
        """
    )
    op.execute(
        """        
        DROP TABLE `track_change_reason`;
        """
    )
