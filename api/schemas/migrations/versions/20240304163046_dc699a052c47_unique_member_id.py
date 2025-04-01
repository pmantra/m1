"""unique_member_id

Revision ID: dc699a052c47
Revises: 534cb29dc8c5
Create Date: 2024-03-04 16:30:46.174871+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "dc699a052c47"
down_revision = "534cb29dc8c5"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `member_health_plan`
        MODIFY `member_id` int(11) NOT NULL,
        DROP KEY `member_id`,
        ADD UNIQUE KEY `unique_member_id_in_plan` (`member_id`, `employer_health_plan_id`), 
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `member_health_plan`
        MODIFY `member_id` int(11) DEFAULT NULL,
        DROP KEY `unique_member_id_in_plan`,
        ADD KEY `member_id` (`member_id`), 
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)
