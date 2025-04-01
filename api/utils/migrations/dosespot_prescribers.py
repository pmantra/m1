import csv
import io

from storage.connection import db


def get_dosespot_prescribers(x_days_ago=120, status_set_to="AVAILABLE"):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    sql = """SELECT DISTINCT u.first_name, u.email
             FROM practitioner_profile pp JOIN `user` u ON (pp.user_id=u.id)
             JOIN `schedule` s ON (s.user_id=pp.user_id)
             JOIN schedule_event se ON (se.schedule_id=s.id)
             WHERE pp.dosespot != '{}'
             AND se.state = :status_set_to
             AND (se.ends_at >= CURDATE() - INTERVAL :x_days_ago DAY OR se.starts_at <= NOW());"""

    results = db.session.execute(
        sql, {"status_set_to": status_set_to, "x_days_ago": x_days_ago}
    )
    prescribers = results.fetchall()
    print(
        "Total %s of practitioners who are dosespot enabled and "
        "set availability in the last %s days" % (len(prescribers), x_days_ago)
    )

    output = io.StringIO()
    headers = ("first_name", "email")
    writer = csv.DictWriter(output, fieldnames=headers)

    writer.writeheader()
    for prescriber in prescribers:
        writer.writerow({"first_name": prescriber[0], "email": prescriber[1]})

    # dump csv content, copy paste it to a csv file
    print(output.getvalue())
    output.close()
