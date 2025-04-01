"""
Job to monitor bills and log if they are stale - i.e have been in a certain state for too long.
"""
import sys

from app import create_app
from utils.log import logger

log = logger(__name__)


def main() -> None:
    with create_app().app_context():
        from direct_payment.billing.tasks.lib.bill_monitoring_functions import (
            monitor_bills,
            monitor_bills_completed_tps,
            monitor_bills_scheduled_tps,
            monitor_failed_bills,
        )

        status = True
        status &= monitor_bills()
        status &= monitor_failed_bills()
        status &= monitor_bills_scheduled_tps()
        status &= monitor_bills_completed_tps()
        sys.exit(int(not status))


if __name__ == "__main__":
    main()
