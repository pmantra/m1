import os

PROCEDURE_BACKDATE_LIMIT_DAYS: int = int(
    os.environ.get("PROCEDURE_BACKDATE_LIMIT_DAYS", 90)
)
