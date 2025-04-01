#!/usr/bin/env python3
import enum
import os
from datetime import timezone
from urllib.parse import quote

import snowflake
from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedModelBase, db
from models.enterprise import UserAsset, UserAssetState
from utils.log import logger

log = logger(__name__)


USER_FILE_BUCKET = os.environ.get("USER_FILE_BUCKET")


class UserFileTypes(enum.Enum):
    BIRTH_PLAN = "BIRTH_PLAN"


class UserFile(TimeLoggedModelBase):
    __tablename__ = "user_file"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(UserFileTypes), nullable=False)
    content_type = Column(String(255), nullable=False)
    gcs_id = Column(String(255), nullable=False)
    user_id = Column(ForeignKey("user.id"))
    appointment_id = Column(ForeignKey("appointment.id"))

    user = relationship("User", backref="files")
    appointment = relationship("Appointment", backref="files")

    def __repr__(self) -> str:
        return f"<UserFile [{self.id}] User ID: {self.user.id}>"

    __str__ = __repr__

    @property
    def gcs_blob(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return UserAsset.client().get_bucket(USER_FILE_BUCKET).get_blob(self.gcs_id)


def migrate():  # type: ignore[no-untyped-def] # Function is missing a return type annotation

    user_files = UserFile.query.all()
    log.info(
        "Migrating user files to user assets.", number_of_user_files=len(user_files)
    )

    # Make sure things are in a reasonable state.
    okay = True
    for f in user_files:
        if f.content_type != "application/pdf":
            log.error(
                "Found non-pdf user file.",
                user_file_id=f.id,
                content_type=f.content_type,
            )
        elif f.appointment is None:
            log.error("Found user file without appointment.", user_file_id=f.id)
        elif not f.gcs_blob.exists():
            log.error("Found user file without blob in bucket.", user_file_id=f.id)
        else:
            continue  # pass
        okay = False  # fail (from above branches)
    if not okay:
        log.info("Stopping user file migration due to misunderstood conditions above.")
        return

    log.debug("Proceeding with migration.")
    for f in user_files:
        asset_id = snowflake.from_datetime(f.created_at.replace(tzinfo=timezone.utc))
        log.debug("Migrating user file.", user_file_id=f.id, asset_id=str(asset_id))

        old_blob = f.gcs_blob
        old_bucket = old_blob.bucket
        new_bucket = UserAsset.bucket()
        new_blob_name = f"o/{asset_id}"

        old_blob.reload()  # grab size metadata

        a = UserAsset(
            id=asset_id,
            user=f.user,
            state=UserAssetState.COMPLETE,
            file_name="MAVEN_BIRTH_PLAN.pdf",
            content_type=f.content_type,
            content_length=old_blob.size,
            appointment=f.appointment,
            modified_at=f.modified_at,
        )

        log.debug(
            "Copying blob from user files bucket to user assets bucket.",
            asset_id=a.external_id,
            old_blob=old_blob.id,
            new_bucket=new_bucket.name,
            new_blob_name=new_blob_name,
        )
        new_blob = old_bucket.copy_blob(old_blob, new_bucket, new_blob_name)
        new_blob.content_type = f.content_type
        new_blob.content_disposition = (
            f"attachment;filename*=utf-8''{quote(a.file_name)}"
        )
        log.debug("Patching new blob metadata.")
        new_blob.patch()

        db.session.add(a)
        db.session.commit()
        log.debug(
            "Migrated user file to user asset.",
            user_file_id=f.id,
            asset_id=a.external_id,
        )

    log.info("All done.")
