from datetime import date, timedelta

from storage.connection import db


def load_metric(ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    metrics = all_metrics()
    charts = []

    for name in ids:
        if name in metrics:
            metric = metrics[name]
            start_date = date.today() - timedelta(days=14)
            end_date = date.today()

            chart = {
                "name": metric["name"],
                "data": metric["query"](start_date, end_date),
            }

            charts.append(chart)

    return charts


def _execute(query):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def run_it(start_date, end_date):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        results = db.session.execute(
            query, {"start_date": start_date, "end_date": end_date}
        )

        data = results.fetchall()

        return {date.strftime("%Y-%m-%d"): count for date, count in data}

    return run_it


def load_metric_names():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    metrics = all_metrics()
    return {id: item["name"] for id, item in metrics.items()}


def all_metrics():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return {
        "created_appointments": {
            "name": "Created appointments",
            "query": _execute(
                """
                select 
                    date(a.created_at), 
                    count(distinct a.id)
                from
                    appointment a
                where
                    (a.created_at < :end_date 
                    AND a.created_at > :start_date)
                group by 1;
                """
            ),
        },
        "appointments_with_post_encounter_summary": {
            "name": "Appointments with Post-Encounter Summary",
            "query": _execute(
                """
                select 
                    date(answer_set.submitted_at), 
                    count(distinct appt.id)
                from
                    appointment appt
                join
                    recorded_answer_set answer_set on answer_set.appointment_id = appt.id
                join
                    practitioner_profile pract on pract.user_id = answer_set.source_user_id
                where
                    appt.scheduled_end < :end_date 
                    AND appt.scheduled_end > :start_date
                group by 1;
                """
            ),
        },
        "providers_with_next_availability_in_future": {
            "name": "Providers with availability in the future (based on next_availability)",
            "query": _execute(
                """
                select 
                    date(pract.next_availability), 
                    count(distinct pract.user_id)
                from
                    practitioner_profile as pract
                where
                    next_availability IS NOT NULL
                    AND pract.next_availability > :start_date
                group by 1;
                """
            ),
        },
        "all_new_messages": {
            "name": "New messages",
            "query": _execute(
                """
                select 
                    date(m.created_at), 
                    count(distinct m.id)
                from
                    message m
                where
                    (m.created_at < :end_date 
                    AND m.created_at > :start_date)
                group by 1;
                """
            ),
        },
        "new_user_flags": {
            "name": "New users with flags",
            "query": _execute(
                """
                select 
                    date(u.created_at),
                    count(distinct u.id)
                from 
                    user u
                left join 
                    user_flag_users as ufu 
                    on ufu.user_id = u.id
                where
                    (u.created_at < :end_date 
                    AND u.created_at > :start_date)
                group by 1;
                """
            ),
        },
    }
