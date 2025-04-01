"""set-provider-lang-eng

Revision ID: 2bd5835beab9
Revises: 27fb94ca8399
Create Date: 2023-09-20 15:48:34.914711+00:00

"""
from storage.connection import db
from sqlalchemy import insert

from models.profiles import Language, PractitionerProfile, practitioner_languages


# revision identifiers, used by Alembic.
revision = "2bd5835beab9"
down_revision = "27fb94ca8399"
branch_labels = None
depends_on = None


def upgrade():
    english = db.session.query(Language).filter(Language.name == Language.ENGLISH).one()
    providers_with_eng = (
        db.session.query(practitioner_languages)
        .filter(practitioner_languages.c.language_id == english.id)
        .all()
    )
    provider_ids_with_english = [x[0] for x in providers_with_eng]
    providers_ids_without_english = (
        db.session.query(PractitionerProfile.user_id)
        .filter(~PractitionerProfile.user_id.in_(provider_ids_with_english))
        .all()
    )
    bulk_update_objs = [
        {"user_id": x[0], "language_id": english.id}
        for x in providers_ids_without_english
    ]

    db.session.execute(
        insert(practitioner_languages),
        bulk_update_objs,
    )
    db.session.commit()


def downgrade():
    pass
