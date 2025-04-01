from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)

log = logger(__name__)


def update_ros_entries():
    try:
        from wallet.migrations.config.backfill_ros_runout_loss_rule import (
            ROS_TO_RUNOUT_LOSS,
        )

        org_settings = ROS_TO_RUNOUT_LOSS
        total_records = len(org_settings)
        log.info(f"Starting migration for {total_records} ROS records")
        processed_records = 0

        # Update records in batches
        batch_size = 100
        for i in range(0, len(org_settings), batch_size):
            batch = {
                k: org_settings[k]
                for k in list(org_settings.keys())[i : i + batch_size]
            }
            log.info(f"Processing batch starting at index {i}")

            for ros_id, settings in batch.items():
                ros = db.session.query(ReimbursementOrganizationSettings).get(ros_id)
                if ros:
                    old_loss_rule = ros.eligibility_loss_rule
                    old_run_out_days = ros.run_out_days

                    ros.eligibility_loss_rule = settings["loss_rule"]
                    ros.run_out_days = settings["run_out_days"]
                    processed_records += 1
                    if processed_records % 10 == 0:  # Log every 10 records
                        log.info(
                            f"Progress: {processed_records}/{total_records} records processed"
                            f" - Updated ROS {ros_id}: loss_rule {old_loss_rule}->{settings['loss_rule']}, "
                            f"run_out_days {old_run_out_days}->{settings['run_out_days']}"
                        )
                else:
                    log.warning(f"ROS ID {ros_id} not found in database")

            db.session.commit()
            db.session.expunge_all()
            log.info(
                f"Committed batch, processed {processed_records}/{total_records} records total"
            )

    except Exception as e:
        log.error(f"Error during migration: {str(e)}")
        db.session.rollback()
        raise e


if __name__ == "__main__":
    from app import create_app

    with create_app(task_instance=True).app_context():
        update_ros_entries()
