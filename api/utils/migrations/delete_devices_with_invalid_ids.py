from models.profiles import Device
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def delete_em(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for device in Device.query.filter(
        Device.device_id.op("not regexp")("^[A-Za-z0-9]+$")
    ).yield_per(1000):
        log.info(
            "Deleting device",
            user_id=device.user_id,
            application_name=device.application_name,
            device_id=device.device_id,
        )
        db.session.delete(device)
    if dry_run:
        db.session.rollback()
        log.debug("Rolled back device deletion!")
    else:
        db.session.commit()
        log.debug("Committed device deletion!")
