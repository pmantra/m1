from typing import List, Optional

from direct_payment.clinic.models.fee_schedule import FeeSchedule
from storage.connection import db
from utils.log import logger
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory

log = logger(__name__)


def duplicate_fee_schedule(
    original_fee_schedule: FeeSchedule,
) -> (List[FlashMessage], bool, Optional[int]):  # type: ignore[syntax] # Syntax error in type annotation
    """
    Duplicates a FeeSchedule and its associated Global Procedures.

    @param original_fee_schedule: The FeeSchedule that is to be duplicated
    @return: A list of flash messages, a bool indicating the success of the duplication attempt and if successful,
             the id of the duplicated FeeSchedule
    """
    messages = []
    try:
        duplicated_fee_schedule = original_fee_schedule.__class__()
        duplicated_fee_schedule.name = f"COPY {original_fee_schedule.name}"
        db.session.add(duplicated_fee_schedule)
        db.session.flush()
    except Exception as e:
        log.exception("duplicate_fee_schedule error duplicating fee schedule", error=e)
        messages.append(
            FlashMessage(
                message="Unable to duplicate Fee Schedule. Please check a copy doesn't already exist.",
                category=FlashMessageCategory.ERROR,
            )
        )
        return messages, False, None

    original_global_procedures = original_fee_schedule.fee_schedule_global_procedures
    duplicated_fsgp_fields = ["reimbursement_wallet_global_procedures_id", "cost"]
    if original_global_procedures:
        try:
            # Duplicate the FeeScheduleGlobalProcedures and update with newly duplicated FeeSchedule id
            for fsgp in original_global_procedures:
                duplicated_fsgp = fsgp.__class__()
                for column in fsgp.__table__.columns:
                    # copy over existing global procedure id and cost
                    if column.name in duplicated_fsgp_fields:
                        setattr(
                            duplicated_fsgp, column.name, getattr(fsgp, column.name)
                        )
                # update FeeScheduleGlobalProcedure object with new FeeSchedule id
                duplicated_fsgp.fee_schedule_id = duplicated_fee_schedule.id
                duplicated_fsgp.fee_schedule = duplicated_fee_schedule
                db.session.add(duplicated_fsgp)
            db.session.commit()
        except Exception as e:
            log.exception(
                "duplicate_fee_schedule error duplicating global procedures", error=e
            )
            messages.append(
                FlashMessage(
                    message="Unable to duplicate Global Procedures.",
                    category=FlashMessageCategory.ERROR,
                )
            )
            db.session.rollback()
            return messages, False, None
    else:
        # commit the empty fee schedule
        db.session.commit()

    messages.append(
        FlashMessage(
            message="Successfully duplicated Fee Schedule!",
            category=FlashMessageCategory.SUCCESS,
        )
    )
    return messages, True, duplicated_fee_schedule.id


def get_user_email_domain(email: str) -> str:
    return email.partition("@")[-1]
