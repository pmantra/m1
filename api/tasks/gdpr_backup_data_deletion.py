import traceback
from datetime import date, timedelta
from typing import List

from models.actions import audit
from models.gdpr import GDPRDeletionBackup
from storage.connection import db
from utils.gdpr_backup_data import GDPRDataDelete
from utils.log import logger

log = logger(__name__)


BACKUP_DELETION_WITHIN_NUM_OF_DAYS = 25
DELETE_AUTH0_USER_AUDIT_TYPE = "Auth0 user deletion"
DELETE_GDPR_DELETION_BACKUP_AUDIT_TYPE = "GDPR backup deletion"


def gdpr_delete_backup(limit=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    backups_to_delete: List[GDPRDeletionBackup] = _get_qualified_backup_to_delete(limit)
    gdpr_data_delete = GDPRDataDelete()

    for backup_to_delete in backups_to_delete:
        log.info(
            "Start deleting GDPR deletion backup",
            id=backup_to_delete.id,
            user_id=backup_to_delete.user_id,
        )

        try:
            _record_in_audit(backup_to_delete, DELETE_AUTH0_USER_AUDIT_TYPE)
            try:
                gdpr_data_delete.delete(backup_to_delete.user_id)
            except Exception:
                pass
            _record_in_audit(backup_to_delete, DELETE_GDPR_DELETION_BACKUP_AUDIT_TYPE)
            _delete_model(backup_to_delete)
        except Exception as e:
            log.error(
                "Error in gdpr_delete_backup",
                error_type=e.__class__.__name__,
                error_msg=str(e),
                id=backup_to_delete.id,
                user_id=backup_to_delete.user_id,
            )
            traceback.print_exc()
        else:
            log.info(
                "Successfully delete GDPR deletion backup",
                id=backup_to_delete.id,
                user_id=backup_to_delete.user_id,
            )


def _get_qualified_backup_to_delete(limit) -> List[GDPRDeletionBackup]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    latest_requested_date: date = date.today() - timedelta(
        BACKUP_DELETION_WITHIN_NUM_OF_DAYS
    )
    log.info(
        f"The latest_requested_date for backup deletion is {latest_requested_date}"
    )
    return (
        GDPRDeletionBackup.query.filter(
            GDPRDeletionBackup.requested_date <= latest_requested_date
        ).all()
        if limit is None
        else GDPRDeletionBackup.query.filter(
            GDPRDeletionBackup.requested_date <= latest_requested_date
        )
        .limit(limit)
        .all()
    )


def _record_in_audit(backup_to_delete: GDPRDeletionBackup, audit_type: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    audit(user_id=backup_to_delete.user_id, action_type=audit_type)


def _delete_model(backup_to_delete: GDPRDeletionBackup):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        db.session.delete(backup_to_delete)
        db.session.commit()
    except Exception as e:
        log.warn(
            "Error deleting GDPR deletion backup",
            id=backup_to_delete.id,
            user_id=backup_to_delete.user_id,
            error_type=e.__class__.__name__,
            error_msg=str(e),
        )
        raise
