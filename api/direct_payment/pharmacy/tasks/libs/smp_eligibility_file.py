import csv
import io
import os
from datetime import datetime, timezone
from io import StringIO
from typing import List

import pytz
import sqlalchemy
from google.cloud.exceptions import GoogleCloudError
from maven import feature_flags

from authn.models.user import User
from direct_payment.pharmacy.constants import (
    ENABLE_SMP_GCS_BUCKET_PROCESSING,
    ENABLE_UNLIMITED_BENEFITS_FOR_SMP,
    QUATRIX_OUTBOUND_BUCKET,
    SMP_BUCKET_NAME,
    SMP_ELIGIBILITY_FILE_PREFIX,
    SMP_FOLDER_NAME,
    SMP_FTP_PASSWORD,
    SMP_FTP_USERNAME,
    SMP_GCP_BUCKET_NAME,
    SMP_HOST,
    SMPMemberType,
)
from direct_payment.pharmacy.tasks.libs.common import list_filenames_today
from direct_payment.pharmacy.tasks.libs.pharmacy_file_handler import PharmacyFileHandler
from direct_payment.pharmacy.utils.gcs_handler import upload_to_gcp_bucket
from storage.connection import db
from utils.log import logger
from wallet.models.constants import WalletState
from wallet.models.reimbursement import ReimbursementRequestCategory
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.health_plan import HealthPlanRepository
from wallet.repository.member_benefit import MemberBenefitRepository
from wallet.services.reimbursement_benefits import find_maven_gold_wallet_user_objs
from wallet.services.reimbursement_wallet import ReimbursementWalletService
from wallet.utils.alegeus.edi_processing.common import ssh_connect
from wallet.utils.annual_questionnaire import utils as questionnaire_utils

log = logger(__name__)

HEADERS = [
    "First_Name",
    "Last_Name",
    "Date_Of_Birth",
    "Maven_Benefit_ID",
    "Employer",
    "Member_Type",
]


def _create_eligibility_file() -> io.StringIO:
    log.info("Creating eligibility file")
    rows = []
    query_results: List = find_maven_gold_wallet_user_objs()

    HEADERS.append("User_Benefit_ID")
    member_benefit_repository = MemberBenefitRepository(session=db.session)
    wallet_service = ReimbursementWalletService()
    enable_unlimited_benefits_for_smp: bool = feature_flags.bool_variation(
        ENABLE_UNLIMITED_BENEFITS_FOR_SMP, default=False
    )

    for query_obj in query_results:
        wallet, wallet_user, org_setting, org = (
            query_obj.ReimbursementWallet,
            query_obj.ReimbursementWalletUsers,
            query_obj.ReimbursementOrganizationSettings,
            query_obj.Organization,
        )
        if wallet.state == WalletState.RUNOUT:
            log.info(
                "Omitting runout wallet to SMP in the eligibility file.",
                wallet_id=str(wallet.id),
            )
            continue

        direct_payment_category = wallet.get_direct_payment_category
        if not direct_payment_category:
            log.info(
                "Omitting wallet with no direct payment category in the eligibility file.",
                wallet_id=str(wallet.id),
            )
            continue

        member = wallet_user.member

        wallet_benefit_id = (
            wallet.reimbursement_wallet_benefit
            and wallet.reimbursement_wallet_benefit.maven_benefit_id
        )
        member_type = _get_smp_eligibility_member_type(
            member=member,
            wallet=wallet,
            direct_payment_category=direct_payment_category,
            org_setting=org_setting,
            wallet_service=wallet_service,
            enable_unlimited=enable_unlimited_benefits_for_smp,
        )
        try:
            user_benefit = member_benefit_repository.get_by_user_id(user_id=member.id)
        except sqlalchemy.orm.exc.NoResultFound:
            log.error(
                "No user benefit found for user.",
                user_id=member.id,
            )
            continue
        except Exception as e:
            log.error(
                "Error retrieving user benefit from database.",
                error=e,
                user_id=member.id,
            )
            continue
        rows.append(
            [
                member.first_name.replace('"', ""),
                member.last_name.replace('"', ""),
                member.health_profile.birthday if member.health_profile else None,
                wallet_benefit_id,
                org.name,
                member_type.value,
                user_benefit.benefit_id,
            ]
        )

    buffer = StringIO()
    csvwriter = csv.writer(buffer, delimiter=",", quoting=csv.QUOTE_ALL)
    csvwriter.writerow(HEADERS)
    csvwriter.writerows(rows)
    log.info("File created successfully.")
    return buffer


def _get_smp_eligibility_member_type(
    member: User,
    wallet: ReimbursementWallet,
    direct_payment_category: ReimbursementRequestCategory,
    org_setting: ReimbursementOrganizationSettings,
    wallet_service: ReimbursementWalletService,
    enable_unlimited: bool,
) -> SMPMemberType:
    if enable_unlimited:
        category_association = direct_payment_category.get_category_association(
            reimbursement_wallet=wallet
        )
        category_balance = wallet_service.get_wallet_category_balance(
            wallet=wallet, category_association=category_association
        )
    else:
        _, remaining_wallet_balance, _ = wallet.get_direct_payment_balances()

    if enable_unlimited and (
        not category_balance.is_unlimited and category_balance.current_balance <= 0
    ):
        return SMPMemberType.GOLD_X
    elif not enable_unlimited and (
        not remaining_wallet_balance or remaining_wallet_balance <= 0
    ):
        return SMPMemberType.GOLD_X
    else:
        if org_setting.rx_direct_payment_enabled:
            # check if the gold user has a current health plan
            member_health_plan = HealthPlanRepository(
                db.session
            ).get_member_plan_by_wallet_and_member_id(
                member_id=member.id,
                wallet_id=wallet.id,
                effective_date=datetime.now(timezone.utc),
            )
            if not member_health_plan:
                if org_setting.deductible_accumulation_enabled:
                    return SMPMemberType.GOLD_X_NO_HEALTH_PLAN
                else:
                    hdhp_status = questionnaire_utils.check_if_is_hdhp(
                        wallet=wallet,
                        user_id=member.id,
                        effective_date=datetime.now(timezone.utc),
                        has_health_plan=False,
                    )
                    if hdhp_status == questionnaire_utils.HDHPCheckResults.HDHP_YES:
                        # HDHP wallets/members require a health plan
                        return SMPMemberType.GOLD_X_NO_HEALTH_PLAN
            return SMPMemberType.GOLD
        else:
            return SMPMemberType.GOLD_REIMBURSEMENT


def ship_eligibility_file_to_smp(dry_run: bool = False) -> bool:
    now = datetime.now(pytz.timezone("America/New_York"))
    date_time = now.strftime("%Y%m%d_%H%M%S")
    file_name = f"{SMP_ELIGIBILITY_FILE_PREFIX}_{date_time}.csv"

    buffer = _create_eligibility_file()
    buffer.seek(0)
    if dry_run:
        with open(file_name, "w") as file:
            file.write(buffer.getvalue())
        return True

    log.info("Start uploading file.")

    if feature_flags.bool_variation(ENABLE_SMP_GCS_BUCKET_PROCESSING, default=False):
        pharmacy_handler = PharmacyFileHandler(
            internal_bucket_name=SMP_GCP_BUCKET_NAME,
            outgoing_bucket_name=QUATRIX_OUTBOUND_BUCKET,
        )
        return pharmacy_handler.upload_eligibility_file(buffer, date_time)

    ssh_client = ssh_connect(
        SMP_HOST, username=SMP_FTP_USERNAME, password=SMP_FTP_PASSWORD, max_attempts=3
    )
    ftp = None
    try:
        ftp = ssh_client.open_sftp()
        files = list_filenames_today(
            ftp=ftp,
            path=f"{SMP_FOLDER_NAME}/MavenGoldEligibility",
            prefix=f'{SMP_ELIGIBILITY_FILE_PREFIX}_{now.strftime("%Y%m%d")}',
        )
        if len(files) >= 3:
            log.error(
                "Found all of today's eligibility files in SMP server! Cancelling job...",
                files=files,
            )
            return False

        ftp.putfo(
            buffer, f"{SMP_FOLDER_NAME}/MavenGoldEligibility/{file_name}", confirm=False
        )
        buffer.seek(0)
        upload_to_gcp_bucket(
            buffer,
            f"{SMP_ELIGIBILITY_FILE_PREFIX}_{date_time}.csv",
            os.environ.get(SMP_BUCKET_NAME),
        )
    except GoogleCloudError as e:
        log.error("Error uploading to GCP bucket.", error=e, file_name=file_name)
    except Exception as e:
        log.error("Unable to upload csv file to SMP SFTP server!", error=e)
        return False
    finally:
        if ftp:
            ftp.close()
        ssh_client.close()
    log.info("File uploaded successfully.")
    return True
