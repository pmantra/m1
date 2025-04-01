from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import Iterable, List, Optional

from direct_payment.pharmacy.tasks.smp_cost_breakdown_audit import (
    ErrorInfo,
    Results,
    RxAudit,
)
from storage.connection import db
from utils.log import logger
from utils.payments import convert_cents_to_dollars

log = logger(__name__)


def _get_results_by_user_id(
    results: Iterable[Results | ErrorInfo], user_id: str
) -> List[Results | ErrorInfo]:
    for result in results:
        if user_id == result.user_id:
            yield result


def _get_error_message_by_treatment_procedure(
    treatment_procedure_id: int, errors: dict
) -> str:
    if treatment_procedure_id in errors:
        error = errors[treatment_procedure_id]
        return error.error_message
    else:
        return ""


def _get_general_errors(errors: dict) -> str:  # type: ignore[return] # Missing return statement
    if "general_error" in errors:
        return errors["general_error"]


def _convert_rx_cents_to_dollars(
    amount: Optional[Decimal | int | str],
) -> Optional[Decimal | int | str]:
    amount_type = type(amount)
    if amount_type == Decimal:
        return amount
    if amount_type == int:
        return f"${convert_cents_to_dollars(amount):.2f}"  # type: ignore[arg-type] # Argument 1 to "convert_cents_to_dollars" has incompatible type "Union[Decimal, int, str, None]"; expected "int"
    return amount


def download_scheduled_file_audit_report(
    file_date: Optional[datetime],
) -> (StringIO, Optional[str]):  # type: ignore[syntax] # Syntax error in type annotation
    rx_audit = RxAudit(session=db.session)
    (
        cost_breakdown_results,
        users,
        errors,
    ) = rx_audit.calculate_cost_breakdown_audit_for_time_range(start_time=file_date)
    log.debug(
        "SMP Audit Results",
        cost_breakdown=cost_breakdown_results,
        user_info=users,
        errors=errors,
    )
    fields = [
        "Member ID",
        "Procedure ID",
        "Procedure Cost",
        "Procedure Category",
        "Procedure name",
        "Procedure Status",
        "Organization Name",
        "Error Message",
        "Benefit ID",
        "Reimbursement Wallet ID",
        "Member Health Plan ID",
        "Subscriber ID",
        "Health Plan Name",
        "Plan type",
        "Is HDHP",
        "Rx integrated",
        "Deductible Embedded",
        "OOPM Embedded",
        "Individual Ded Limit",
        "Family Ded Limit",
        "Individual OOP Limit",
        "Family OOP Limit",
        "Cost Share",
        "Coinsurance Min",
        "Coinsurance Max",
        "Individual Ded YTD",
        "Individual OOPM YTD",
        "Family Ded YTD",
        "Family OOPM YTD",
        "Deductible Applied",
        "Coinsurance Applied",
        "Copay Applied",
        "Not Covered",
        "OOP Applied",
        "Deductible Remaining Pre CB",
        "OOPM Remaining Pre CB",
        "Member responsibility",
        "Employer responsibility",
        "Total Member Charges YTD",
        "Total Family Charges YTD",
    ]

    rows = []
    for user_id, user_info in users.items():
        results = _get_results_by_user_id(
            results=cost_breakdown_results, user_id=user_id
        )
        for result in results:
            error_message = _get_error_message_by_treatment_procedure(
                treatment_procedure_id=result.treatment_procedure_id, errors=errors
            )
            if isinstance(result, ErrorInfo):
                rows.append(
                    [
                        user_info.user_id,
                        result.treatment_procedure_id,
                        _convert_rx_cents_to_dollars(int(result.price)),
                        result.category,
                        result.drug_name,
                        result.status,
                        user_info.org_name,
                        error_message,
                        user_info.benefit_id,
                        user_info.wallet_id,
                        result.member_health_plan_id,
                        result.subscriber_id,
                        result.employer_health_plan_name,
                        result.is_family_plan,
                        result.is_hdhp,
                        result.rx_integrated,
                        result.deductible_embedded,
                        result.oopm_embedded,
                        _convert_rx_cents_to_dollars(result.ind_ded_limit),
                        _convert_rx_cents_to_dollars(result.fam_ded_limit),
                        _convert_rx_cents_to_dollars(result.ind_oopm_limit),
                        _convert_rx_cents_to_dollars(result.fam_oopm_limit),
                    ]
                )
            else:
                rows.append(
                    [
                        user_info.user_id,
                        result.treatment_procedure_id,
                        _convert_rx_cents_to_dollars(int(result.price)),
                        result.category,
                        result.drug_name,
                        result.status,
                        user_info.org_name,
                        error_message,
                        user_info.benefit_id,
                        user_info.wallet_id,
                        user_info.member_health_plan_id,
                        user_info.subscriber_id,
                        user_info.employer_health_plan_name,
                        user_info.is_family_plan,
                        user_info.is_hdhp,
                        user_info.rx_integrated,
                        user_info.deductible_embedded,
                        user_info.oopm_embedded,
                        _convert_rx_cents_to_dollars(user_info.ind_ded_limit),
                        _convert_rx_cents_to_dollars(user_info.fam_ded_limit),
                        _convert_rx_cents_to_dollars(user_info.ind_oopm_limit),
                        _convert_rx_cents_to_dollars(user_info.fam_oopm_limit),
                        _convert_rx_cents_to_dollars(result.cost_share),
                        _convert_rx_cents_to_dollars(result.cost_share_min),
                        _convert_rx_cents_to_dollars(result.cost_share_max),
                        _convert_rx_cents_to_dollars(user_info.ind_ded_ytd),
                        _convert_rx_cents_to_dollars(user_info.ind_oopm_ytd),
                        _convert_rx_cents_to_dollars(user_info.fam_ded_ytd),
                        _convert_rx_cents_to_dollars(user_info.fam_oopm_ytd),
                        _convert_rx_cents_to_dollars(result.applied_to_deductible),
                        _convert_rx_cents_to_dollars(result.applied_to_coinsurance),
                        _convert_rx_cents_to_dollars(result.applied_to_copay),
                        _convert_rx_cents_to_dollars(result.not_covered),
                        _convert_rx_cents_to_dollars(result.oop_applied),
                        _convert_rx_cents_to_dollars(
                            result.deductible_remaining_pre_cb
                        ),
                        _convert_rx_cents_to_dollars(result.oop_remaining_pre_cb),
                        _convert_rx_cents_to_dollars(result.total_member_resp),
                        _convert_rx_cents_to_dollars(result.total_employer_resp),
                        _convert_rx_cents_to_dollars(result.member_ytd_charges),
                        _convert_rx_cents_to_dollars(result.family_ytd_charges),
                    ]
                )
    general_errors = _get_general_errors(errors)

    # Create File
    smp_audit = StringIO()
    csvwriter = csv.writer(smp_audit, delimiter=",")
    csvwriter.writerow(fields)
    csvwriter.writerows(rows)
    log.info("Audit File created successfully.")
    return smp_audit, general_errors
