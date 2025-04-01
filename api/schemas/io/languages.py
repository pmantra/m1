from models.profiles import Language
from storage.connection import db


def restore() -> None:
    defaults = [
        {"name": "English"},
        {"name": "Spanish"},
        {"name": "French"},
        {"name": "Portuguese"},
        {"name": "Korean"},
        {"name": "Japanese"},
        {"name": "Mandarin"},
        {"name": "Cantonese"},
        {"name": "Thai"},
    ]
    db.session.bulk_insert_mappings(Language, defaults)
