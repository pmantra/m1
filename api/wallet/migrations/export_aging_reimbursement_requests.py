import csv
from datetime import datetime

from app import create_app
from storage.connection import db
from utils.log import logger

log = logger(__name__)

EXPORT_FILENAME = f"/tmp/export_{datetime.utcnow().isoformat()}"

QUERY_PRE_2024 = """
select
    rr.id as reimbursement_request_id,
    rr.state as reimbursement_request_state,
    rr.reimbursement_wallet_id as reimbursement_wallet_id,
    rwu.zendesk_ticket_id as zendesk_ticket_id,
    ros.organization_id as organization_id,
    rr.person_receiving_service as person_receiving_service,
    rr.person_receiving_service_id as person_receiving_service_id,
    rr.label as reimbursement_request_label,
    rrc.label as category_label,
    rr.description as description,
    rr.procedure_type as procedure_type,
    rr.amount as amount_cents,
    rr.amount / 100 as amount_dollars,
    rr.benefit_currency_code as currency,
    rr.created_at as submitted_at
from reimbursement_request rr
inner join reimbursement_request_category rrc
    on rr.reimbursement_request_category_id = rrc.id
inner join reimbursement_wallet rw
    on rr.reimbursement_wallet_id = rw.id
inner join reimbursement_organization_settings ros
    on rw.reimbursement_organization_settings_id = ros.id
inner join reimbursement_wallet_users rwu
    on rw.id = rwu.reimbursement_wallet_id
where rr.state = 'NEW'
    -- submitted in 2024
    and YEAR(rr.created_at) < 2024
order by rr.created_at asc;
"""

QUERY_2024 = """
select
    rr.id as reimbursement_request_id,
    rr.state as reimbursement_request_state,
    rr.reimbursement_wallet_id as reimbursement_wallet_id,
    rwu.zendesk_ticket_id as zendesk_ticket_id,
    ros.organization_id as organization_id,
    rr.person_receiving_service as person_receiving_service,
    rr.person_receiving_service_id as person_receiving_service_id,
    rr.label as reimbursement_request_label,
    rrc.label as category_label,
    rr.description as description,
    rr.procedure_type as procedure_type,
    rr.amount as amount_cents,
    rr.amount / 100 as amount_dollars,
    rr.benefit_currency_code as currency,
    rr.created_at as submitted_at
from reimbursement_request rr
inner join reimbursement_request_category rrc
    on rr.reimbursement_request_category_id = rrc.id
inner join reimbursement_wallet rw
    on rr.reimbursement_wallet_id = rw.id
inner join reimbursement_organization_settings ros
    on rw.reimbursement_organization_settings_id = ros.id
inner join reimbursement_wallet_users rwu
    on rw.id = rwu.reimbursement_wallet_id
where rr.state = 'NEW'
    -- submitted in 2024
    and YEAR(rr.created_at) = 2024
    -- more than 30 days old
    and rr.created_at < DATE_SUB(current_timestamp, INTERVAL 30 DAY)
    -- need in the description
    and lower(rr.description) like '%need%'
order by rr.created_at asc;
"""


def export_pre_2024():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    results = db.session.execute(QUERY_PRE_2024).fetchall()
    dict_results: list[dict] = [dict(r) for r in results]

    if not dict_results:
        log.info("Nothing found...exiting...")
        return

    # open a csv file and write the results there
    with open(EXPORT_FILENAME, "w", newline="") as csvfile:
        fieldnames = list(dict_results[0].keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        for row in dict_results:
            writer.writerow(row)


def export_2024():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    results = db.session.execute(QUERY_2024).fetchall()
    dict_results: list[dict] = [dict(r) for r in results]

    if not dict_results:
        log.info("Nothing found...exiting...")
        return

    # open a csv file and write the results there
    with open(EXPORT_FILENAME, "w", newline="") as csvfile:
        fieldnames = list(dict_results[0].keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        for row in dict_results:
            writer.writerow(row)


if __name__ == "__main__":
    with create_app().app_context():
        export_pre_2024()
        export_2024()
