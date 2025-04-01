"""PAY-4803-meta-table

Revision ID: 96c4b2926832
Revises: dc68bccb9001
Create Date: 2023-10-23 14:58:02.410457+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "96c4b2926832"
down_revision = "dc68bccb9001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `ingestion_meta` (
            `task_id` int PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `most_recent_raw` varchar(128),
            `most_recent_parsed` varchar(128),
            `task_started_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            `task_updated_at` TIMESTAMP NULL,
            `created_at` datetime DEFAULT NULL,
            `modified_at` datetime DEFAULT NULL,
            `task_status` enum('SUCCESS', 'INPROGRESS', 'FAILED') default 'INPROGRESS',
            `max_tries` int,
            `duration_in_secs` int ,
            `task_type` enum('INCREMENTAL', 'FIXUP') default 'INCREMENTAL',
            `job_type` enum('INGESTION', 'PARSER') default 'INGESTION',
            `target_file` varchar(1024),
            KEY (task_updated_at),
            KEY (task_started_at)
        )
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `ingestion_meta` CASCADE ;
        """
    )
