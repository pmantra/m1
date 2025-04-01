"""
Job to automatically generate wallet reports based on cadence + day_of_week for each organization's report config.
"""

import argparse
import datetime
import sys
from typing import List

from dateutil.relativedelta import relativedelta

from app import create_app
from tasks.queues import job
from utils.log import logger
from wallet.models.constants import WalletReportConfigCadenceTypes
from wallet.models.reimbursement_wallet_report import (
    WalletClientReportConfiguration,
    WalletClientReports,
)
from wallet.services.wallet_client_reporting import create_wallet_report

log = logger(__name__)


def main() -> None:
    args = _generate_args()
    with create_app().app_context():
        status = execute_job(args.dry_run)
    sys.exit(status)


def _generate_args():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        type=lambda x: {"true": True, "false": False}[x],
        required=True,
        help="True will print the organizations that reports would be generated for, and how many reimbursements are processed.",
    )
    args = parser.parse_args()
    return args


def execute_job(dry_run: bool) -> bool:
    log.info("Wallet reporting Job Started.")
    success = generate_wallet_reports(dry_run=dry_run)
    if success:
        log.info("Wallet reporting Job Succeeded.")
    else:
        log.error("Wallet reporting Job Failed.")
    return not success


@job(service_ns="wallet_reporting", team_ns="payments_platform")
def generate_wallet_reports(dry_run: bool = False) -> bool:
    """
    Look for wallet reporting configurations where we match today's date.
    1) If monthly reporting config, match day_of_week to today's date
    2) If biweekly reporting config, figure out which week we're in.
        If odd week, we're matching today's numeric day from 1-7. (1 = Monday, 7 = Sunday)
        if even week, we're matching today's numeric day from 8-14. (8 = Monday, 14 = Sunday)
    3) If weekly reporting config, match day_of_week to today. (1 = Monday, 7 = Sunday)
    """
    today = datetime.datetime.today()
    todays_report_configs: list[WalletClientReportConfiguration] = (
        _get_monthly_report_configs(today)
        + _get_biweekly_report_configs(today)
        + _get_weekly_report_configs(today)
    )
    for config in todays_report_configs:
        if dry_run:
            log.info(
                f'{today.strftime("%Y-%m-%d")} reports: Config[{config.id}] Cadence {config.cadence} day_of_week {config.day_of_week}'
            )
        else:
            start_date = _get_start_date_for_report(today, config)
            create_wallet_report(
                config=config,
                start_date=start_date,
                end_date=today - datetime.timedelta(days=1),
                client_submission_date=today,
                skip_if_empty=True,
            )
    return True


def _get_monthly_report_configs(
    today: datetime.datetime,
) -> List[WalletClientReportConfiguration]:
    day_of_week = today.date().day
    # if today is the last day of the month, grab all configs with day_of_week from today up until the 31st
    if (today + datetime.timedelta(days=1)).month != today.month:
        days = list(range(day_of_week, 32))
        configs = WalletClientReportConfiguration.query.filter(
            WalletClientReportConfiguration.cadence
            == WalletReportConfigCadenceTypes.MONTHLY,
            WalletClientReportConfiguration.day_of_week.in_(days),
        ).all()
    else:
        configs = WalletClientReportConfiguration.query.filter_by(
            cadence=WalletReportConfigCadenceTypes.MONTHLY, day_of_week=day_of_week
        ).all()
    return configs


def _get_biweekly_report_configs(
    today: datetime.datetime,
) -> List[WalletClientReportConfiguration]:
    day_of_week = today.isoweekday()
    week_of_year = int(today.strftime("%V"))
    if week_of_year % 2 == 0:
        day_of_week += 7
    return WalletClientReportConfiguration.query.filter_by(
        cadence=WalletReportConfigCadenceTypes.BIWEEKLY, day_of_week=day_of_week
    ).all()


def _get_weekly_report_configs(
    today: datetime.datetime,
) -> List[WalletClientReportConfiguration]:
    day_of_week = today.isoweekday()
    return WalletClientReportConfiguration.query.filter_by(
        cadence=WalletReportConfigCadenceTypes.WEEKLY, day_of_week=day_of_week
    ).all()


def _get_start_date_for_report(
    today: datetime.datetime, config: WalletClientReportConfiguration
) -> datetime.date:
    last_report = (
        WalletClientReports.query.filter_by(
            organization_id=config.organization_id, configuration_id=config.id
        )
        .order_by(WalletClientReports.end_date.desc())
        .first()
    )
    if last_report:
        start_date = last_report.client_submission_date
    else:
        cadence = config.cadence
        if cadence == WalletReportConfigCadenceTypes.MONTHLY:
            start_date = today - relativedelta(months=1)
        elif cadence == WalletReportConfigCadenceTypes.BIWEEKLY:
            start_date = today - datetime.timedelta(days=14)
        else:
            start_date = today - datetime.timedelta(days=7)
    return start_date


if __name__ == "__main__":
    main()
