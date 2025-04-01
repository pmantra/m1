import datetime
from decimal import Decimal, localcontext

from utils.log import logger

log = logger(__name__)


def convert_rows(rows):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("Got %s rows to convert for stripe to quickbooks", len(rows))
    with localcontext() as ctx:
        ctx.prec = 4
        return _convert_rows(rows)


def _convert_rows(rows):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    payment_fees_by_month = {}
    transfer_fees_by_month = {}
    output = []
    final_output = []
    bad_transfer_ids = []

    for row in rows:
        _skip = False

        _type = row["Type"].upper()
        date_time = row["Created (UTC)"]
        fees = Decimal(row["Fee"])

        transfer_id = None

        if _type == "CHARGE":
            amount = row["Amount"].replace(",", "")
            description = row.get("Description") or "Maven Clinic Billing"
            payment_fees_by_month = add_fees(date_time, fees, payment_fees_by_month)
        elif _type == "REFUND":
            amount = row["Amount"].replace(",", "")
            description = row.get("Description") or "Maven Clinic Billing (Refund)"
            payment_fees_by_month = add_fees(date_time, fees, payment_fees_by_month)
        elif _type == "ADJUSTMENT":
            amount = row["Amount"].replace(",", "")
            description = row.get("Description") or "Maven Clinic Billing (Adjustment)"
            payment_fees_by_month = add_fees(date_time, fees, payment_fees_by_month)
        elif _type == "TRANSFER":
            amount = row["Amount"].replace(",", "")
            description = row.get("Description") or "Transfer from Maven Clinic"
            transfer_fees_by_month = add_fees(date_time, fees, transfer_fees_by_month)
            transfer_id = row["Source"]

        elif _type == "TRANSFER_FAILURE":
            _skip = True
            transfer_fees_by_month = add_fees(date_time, fees, transfer_fees_by_month)
            bad_transfer_ids.append(row["Source"])

        if not _skip:
            output.append(
                {
                    "date_time": date_time,
                    "amount": amount,
                    "description": description,
                    "transfer_id": transfer_id,
                }
            )

    for date, amount in payment_fees_by_month.items():
        output.append(
            {"date_time": date, "amount": amount, "description": "PAYMENT FEES"}
        )

    for date, amount in transfer_fees_by_month.items():
        output.append(
            {"date_time": date, "amount": amount, "description": "TRANSFER FEES"}
        )

    for _ in output:
        if _.get("transfer_id") in bad_transfer_ids:
            continue
        final_output.append(_)

    return final_output


def add_fees(date_time, fee_amount, fee_dict):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    fee_amount = fee_amount * -1

    if fee_amount != 0:
        created_at = datetime.datetime.strptime(date_time, "%Y-%m-%d  %H:%M")
        fee_key = f"{created_at.month}/01/{created_at.year} 00:00"

        if fee_key in fee_dict:
            fee_dict[fee_key] += fee_amount
        else:
            fee_dict[fee_key] = fee_amount

    return fee_dict
