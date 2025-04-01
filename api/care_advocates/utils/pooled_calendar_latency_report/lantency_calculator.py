import csv as csv_module
import io

from authn.models.user import User
from storage.connection import db
from tracks.service import TrackSelectionService
from utils.log import logger
from utils.mail import send_message

CSV_FILE_PROD = (
    "care_advocates/utils/pooled_calendar_latency_report/latency_data_prod.csv"
)
CSV_FILE_QA2 = (
    "care_advocates/utils/pooled_calendar_latency_report/latency_data_qa2.csv"
)

log = logger(__name__)


def calculate_latency(env):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    # List of rows to report
    report_rows = []
    report_rows.append(["latency", "n_cas", "ca_ids", "member_track"])

    if env == "prod":
        CSV_FILE = CSV_FILE_PROD
    elif env == "qa2":
        CSV_FILE = CSV_FILE_QA2
    else:
        log.warning("env must be prod or qa2")
        return

    # Open file with latency data
    with open(CSV_FILE, newline="") as csvfile:
        reader = csv_module.reader(csvfile)
        for row in reader:
            # Skipe first row which has headers
            if row[0] == "Date":
                continue

            # Get latency
            # Latency comes in the shape "12.43ms" or "2.29s", so we need to parse it
            latency_str = row[3]

            if latency_str[-3] == "m":  # Case of ms
                # remove first char and last 3 chats
                latency = float(latency_str[1:-3])
            else:  # Case of s
                # remove first char and last two chars, plus multiply by 1000
                latency = float(latency_str[1:-2]) * 1000

            # Get CAs
            url_str = row[13]
            ca_ids = [
                int(ca_id)
                for ca_id in url_str.split("ca_ids=")[1].split("&")[0].split(",")
            ]
            n_cas = len(ca_ids)

            # Get member track
            # First we need the user
            if not row[9]:  # In some weird cases we dont have the user_id record
                continue
            user_id = int(row[9])
            user = db.session.query(User).get(user_id)
            if not user:
                log.warning("User not found", user_id=user_id)
                return

            user_tracks = user.active_tracks
            highest_priority_track = TrackSelectionService().get_highest_priority_track(
                user_tracks
            )
            highest_priority_track_name = highest_priority_track.name  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrack]" has no attribute "name"

            # Create row with data
            report_rows.append([latency, n_cas, ca_ids, highest_priority_track_name])  # type: ignore[list-item] # List item 0 has incompatible type "float"; expected "str" #type: ignore[list-item] # List item 1 has incompatible type "int"; expected "str" #type: ignore[list-item] # List item 2 has incompatible type "List[int]"; expected "str"

    # Generate csv report
    csv_stream = io.StringIO()
    csv_writer = csv_module.writer(csv_stream, quoting=csv_module.QUOTE_NONNUMERIC)

    for report_row in report_rows:
        csv_writer.writerow(report_row)
    csv = csv_stream.getvalue()

    # Send csv in an email
    send_message(
        to_email="felipe.alamos@mavenclinic.com",
        subject=f"Pooled calendar latency report for env: {env}",
        html="Pooled calendar latency report is attached",
        internal_alert=True,
        production_only=False,
        csv_attachments=[(f"latency_report_{env}.csv", csv)],
    )
