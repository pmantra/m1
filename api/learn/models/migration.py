import enum


class ContentfulMigrationStatus(enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    LIVE = "LIVE"
