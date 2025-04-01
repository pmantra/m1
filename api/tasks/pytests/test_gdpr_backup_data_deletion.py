from datetime import date, timedelta
from typing import List

from models.gdpr import GDPRDeletionBackup
from storage.connection import db
from tasks.gdpr_backup_data_deletion import (
    BACKUP_DELETION_WITHIN_NUM_OF_DAYS,
    gdpr_delete_backup,
)
from utils.random_string import generate_random_string


def test_gdpr_delete_backup(factories):
    user_id_one = int(
        generate_random_string(
            6,
            include_lower_case_char=False,
            include_upper_case_char=False,
            include_digit=True,
        )
    )
    factories.GDPRDeletionBackupFactory.create(
        user_id=user_id_one,
        requested_date=date.today() - timedelta(BACKUP_DELETION_WITHIN_NUM_OF_DAYS + 1),
    )

    user_id_two = int(
        generate_random_string(
            6,
            include_lower_case_char=False,
            include_upper_case_char=False,
            include_digit=True,
        )
    )
    factories.GDPRDeletionBackupFactory.create(
        user_id=user_id_two,
        requested_date=date.today() - timedelta(BACKUP_DELETION_WITHIN_NUM_OF_DAYS + 2),
    )

    user_id_three = int(
        generate_random_string(
            6,
            include_lower_case_char=False,
            include_upper_case_char=False,
            include_digit=True,
        )
    )
    factories.GDPRDeletionBackupFactory.create(
        user_id=user_id_three,
        requested_date=date.today() - timedelta(BACKUP_DELETION_WITHIN_NUM_OF_DAYS - 1),
    )

    backups_before_deletion: List[GDPRDeletionBackup] = db.session.query(
        GDPRDeletionBackup
    ).all()
    assert len(backups_before_deletion) == 3

    gdpr_delete_backup()

    backups_after_deletion: List[GDPRDeletionBackup] = db.session.query(
        GDPRDeletionBackup
    ).all()
    assert len(backups_after_deletion) == 1

    assert backups_after_deletion[0].user_id == user_id_three
