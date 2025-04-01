"""Rewrite P&G unique_corp_id to use subscriber_id

Revision ID: c046f39d48aa
Revises: 51abacd7d153
Create Date: 2023-06-27 20:11:37.952575+00:00

"""
import json

from alembic import op
from sqlalchemy.sql import table, column
from sqlalchemy import String, Integer

from utils import log as logging

# revision identifiers, used by Alembic.
revision = "c046f39d48aa"
down_revision = "51abacd7d153"
branch_labels = None
depends_on = None

P_G_ORG_ID = 348
BATCH_SIZE = 10


logger = logging.logger(__name__)


def chunk(seq, size):
    return (seq[pos : pos + size] for pos in range(0, len(seq), size))


def upgrade():
    # Get initial ID
    records_to_update = op.get_bind().execute(
        oe_table.select().where(
            oe_table.c.organization_id == op.inline_literal(P_G_ORG_ID)
        )
    )
    updates = []
    for record in records_to_update:
        record_json = json.loads(record.json)
        subscriber_id = record_json.get("subscriberId")
        unique_corp_id = record.unique_corp_id
        member_id = record_json.get("memberId")

        # Raise an alert if we don't see any subscriberID = all records should have them
        if not subscriber_id or subscriber_id == "":
            logger.error(
                "Encountered a P&G org employee record without a subscriberID",
                id=record.id,
                unique_corp_id=unique_corp_id,
            )
            continue

        # No records should have memberID populated anymore
        if member_id and member_id != "":
            logger.error(
                "Encountered a P&G org employee record *WITH* memberId populated",
                id=record.id,
                unique_corp_id=unique_corp_id,
            )

        # Update any record we see where we aren't using subscriberID for unique_corp_id.
        # Optum should have been using subscriberID to begin with, but mapped everything to memberID instead
        if unique_corp_id != subscriber_id:
            record.unique_corp_id = subscriber_id
            logger.info(
                "For P&G- Updated unique_corp_id",
                id=record.id,
            )
            updates.append({"id": record.id, "subscriber_id": subscriber_id})

    for group in chunk(updates, BATCH_SIZE):
        for update in group:
            op.execute(
                table.update()
                .where(table.c.id == op.inline_literal(update["id"]))
                .values({"unique_corp_id": op.inline_literal(update["subscriber_id"])})
            )


oe_table = table(
    "organization_employee",
    column("id", Integer),
    column("organization_id", Integer),
    column("unique_corp_id", String),
    column("json", String),
)


def downgrade():
    pass
