"""alter_matching_rule_entity_drop_entity_id

Revision ID: 919cd4e12d91
Revises: ae9bf1ee0d8b
Create Date: 2023-03-01 16:22:59.109045+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "919cd4e12d91"
down_revision = "ae9bf1ee0d8b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET SESSION unique_checks = 0")
    op.execute("SET SESSION foreign_key_checks = 0")
    op.execute(
        """
        ALTER TABLE matching_rule_entity
        DROP INDEX ix_matching_rule_entity_matching_rule_id,
        ADD INDEX ix_matching_rule_entity_matching_rule_id 
            (matching_rule_id, entity_identifier),
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
    op.execute(
        """
        ALTER TABLE matching_rule_entity
        DROP COLUMN entity_id,
        ALGORITHM=COPY
        """
    )
    op.execute("SET SESSION unique_checks = 1")
    op.execute("SET SESSION foreign_key_checks = 1")


def downgrade():
    op.execute("SET SESSION unique_checks = 0")
    op.execute("SET SESSION foreign_key_checks = 0")
    op.execute(
        """
        ALTER TABLE matching_rule_entity
        ADD COLUMN entity_id int(11) DEFAULT NULL AFTER matching_rule_id,
        ALGORITHM=COPY
        """
    )
    op.execute(
        """
        ALTER TABLE matching_rule_entity
        DROP INDEX ix_matching_rule_entity_matching_rule_id,
        ADD INDEX ix_matching_rule_entity_matching_rule_id 
            (matching_rule_id, entity_id, entity_identifier),
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
    op.execute("SET SESSION unique_checks = 1")
    op.execute("SET SESSION foreign_key_checks = 1")
