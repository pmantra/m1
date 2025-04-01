"""add_primary_key_id_field

Revision ID: da10bf948a17
Revises: 7c35f37a173e
Create Date: 2024-01-22 20:42:27.356446+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "da10bf948a17"
down_revision = "7c35f37a173e"
branch_labels = None
depends_on = None


def upgrade():
    # Add a new ID field as the primary key
    op.execute(
        """
         ALTER TABLE wallet_client_report_reimbursements
         ADD COLUMN id INT AUTO_INCREMENT NOT NULL,
         ADD PRIMARY KEY (id),
         ALGORITHM=INPLACE, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        -- Drop the id column
        ALTER TABLE wallet_client_report_reimbursements 
        DROP COLUMN id,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
