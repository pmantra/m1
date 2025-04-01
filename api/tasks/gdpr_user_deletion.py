import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pytz
from google.cloud import storage

from authn.models.user import User
from storage.connection import db
from tasks.constants import get_env_name, get_gdpr_deletion_initiator_user_id
from utils.data_management import gdpr_delete_user
from utils.log import logger

log = logger(__name__)


@dataclass
class DeletedUser:
    user_id: int
    email: str
    requested_date: str  # in the format of MM/DD/YYYY
    delete_idp: bool


def gdpr_delete_users(caller_user_id: Optional[int] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    initiator: Optional[User] = _get_initiator(caller_user_id)
    if initiator is None:
        log.error(f"The initiator is not found by id {caller_user_id}")
        return

    deleted_users: list[DeletedUser] = _create_deleted_users_from_gcs(
        bucket_name=f"new-gdpr-user-deletion-request-{get_env_name()}"
    )

    for deleted_user in deleted_users:
        log.info(f"Start GDPR deletion for user: {deleted_user.user_id}")
        _delete_user(initiator, deleted_user)
        log.info(f"Finish GDPR deletion for user: {deleted_user.user_id}")


def _delete_user(initiator: User, deleted_user: DeletedUser):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        gdpr_delete_user(
            "YES_I_AM_SURE",
            initiator,
            deleted_user.user_id,
            deleted_user.email,
            datetime.strptime(deleted_user.requested_date, "%m/%d/%Y").date(),
            delete_idp=deleted_user.delete_idp,
        )
    except Exception as e:
        log.warning(
            "Error in calling gdpr_delete_user",
            deleted_user_id=deleted_user.user_id,
            error_type=e.__class__.__name__,
            error_message=str(e),
        )
        return

    try:
        db.session.commit()
    except Exception as e:
        log.warning(
            "Error writing to DB while committing user deletion in gdpr_delete_users",
            deleted_user_id=deleted_user.user_id,
            error_type=e.__class__.__name__,
            error_message=str(e),
        )
    else:
        log.info(
            "Successful delete user in gdpr_delete_users",
            user_id=deleted_user.user_id,
        )


def _get_initiator(user_id: Optional[int] = None) -> Optional[User]:
    gdpr_deletion_initiator_user_id = user_id

    if gdpr_deletion_initiator_user_id is None:
        gdpr_deletion_initiator_user_id = get_gdpr_deletion_initiator_user_id()

    if gdpr_deletion_initiator_user_id is not None:
        try:
            log.info(f"The initiator user id is: {gdpr_deletion_initiator_user_id}")
            return User.query.filter_by(id=gdpr_deletion_initiator_user_id).first()
        except Exception as e:
            log.warning(
                "Error in retrieving initiator user id",
                initatior_user_id=gdpr_deletion_initiator_user_id,
                error_type=e.__class__.__name__,
                error_message=str(e),
            )
            return None

    return None


def _create_deleted_users(request_file_path: str) -> List[DeletedUser]:
    all_deleted_users = []

    try:
        with open(request_file_path, "r") as csv_file:
            reader = csv.reader(csv_file, delimiter="\t")

            for row in reader:
                deleted_user = _create_deleted_user(row)
                if deleted_user is not None:
                    all_deleted_users.append(deleted_user)
    except Exception as e:
        log.warning(
            f"Error in finding or processing the file {request_file_path} with GDPR user deletion requests",
            error_type=e.__class__.__name__,
            error_message=str(e),
        )
        return all_deleted_users

    return all_deleted_users


def _create_deleted_users_from_gcs(bucket_name: str) -> List[DeletedUser]:
    current_date = datetime.now(pytz.timezone("America/New_York")).strftime("%Y%m%d")
    file_name = f"gdpr_user_deletion-{current_date}.csv"

    try:
        all_deleted_users = []
        storage_client = storage.Client()

        log.info(
            f"Looking for the file in GCS. Bucket name: {bucket_name}. File name: {file_name}"
        )

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        csv_content = blob.download_as_string()

        csv_rows = csv_content.split(b"\r\n")
        for csv_row in csv_rows:
            deleted_user = _create_deleted_user(
                str(csv_row, encoding="utf-8").split(",")
            )
            if deleted_user is not None:
                all_deleted_users.append(deleted_user)

        return all_deleted_users
    except Exception as e:
        log.warning(
            f"Error in parsing the file {file_name} in GCS with GDPR user deletion requests",
            error_type=e.__class__.__name__,
            error_message=str(e),
        )
        return []


def _create_deleted_user(row: List[str]) -> Optional[DeletedUser]:
    if len(row) == 3:
        return DeletedUser(
            user_id=int(row[1]), email=row[2], requested_date=row[0], delete_idp=True
        )
    else:
        log.error("Invalid record of a GDPR user deletion request", row=row)
        return None
