""" Refactor user.sms_phone_number to use E.164 encoding rather than RFC3966

Revision ID: afcf01696a4d
Revises: feb85e69b8b3
Create Date: 2022-10-28 18:51:35.158191+00:00


Per documentation:

E164 format is as per INTERNATIONAL format but with no formatting applied, e.g. "+41446681800".


RFC3966 is as per INTERNATIONAL format, but with all spaces and other separating symbols
replaced with a hyphen, and with any phone number extension appended with ";ext=".
It also will have a prefix of "tel:" added, e.g. "tel:+41-44-668-1800".


To convert between the two, we will strip out the 'tel' prefix, any `;ext=` suffix, and any dashes



"""
from alembic import op
from authn.models import user
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "afcf01696a4d"
down_revision = "feb85e69b8b3"
branch_labels = None
depends_on = None


NUM_CHUNKS = 10


def update_table():
    # Get initial ID
    user_table_name = user.User.__tablename__

    max_id = db.session.execute(f"SELECT MAX(id) FROM {user_table_name}").fetchall()[0][
        0
    ]

    min_id = db.session.execute(f"SELECT MIN(id) FROM {user_table_name}").fetchall()[0][
        0
    ]

    db.session.close()

    # In the case we do not have any data in our DB, we want to exit the migration
    if not max_id or not min_id:
        return

    size_diff = max_id - min_id

    if size_diff == 0 or size_diff < NUM_CHUNKS:
        range_list = [min_id]
    else:
        chunk_size = round(size_diff / NUM_CHUNKS)
        range_list = list(range(min_id, max_id, chunk_size))

    # Get 1 higher than the max ID to ensure the highest value is updated
    range_list.append(max_id + 1)

    for i, num in enumerate(range_list[:-1]):
        chunk_min = num
        chunk_max = range_list[i + 1]
        update_chunk(table_name=user_table_name, start_id=chunk_min, end_id=chunk_max)


def update_chunk(table_name, start_id, end_id):
    chunk_statement = (
        f" UPDATE "
        f"  {table_name}"
        f" set "
        f"   sms_phone_number = replace("
        f"     replace("
        f"       replace(sms_phone_number, 'tel:', ''), "  # Remove the tel prefix
        f"       ';ext=', "  # Remove any extensions
        f"       ''"
        f"     ), "
        f"     '-', "  # Remove any dashes
        f"     ''"
        f"   ) "
        f" where "
        f"   sms_phone_number is not null "
        f"   and id >= {start_id} "
        f"   and id < {end_id}"
    )
    op.execute(chunk_statement)


def upgrade():
    update_table()


def downgrade():
    pass
