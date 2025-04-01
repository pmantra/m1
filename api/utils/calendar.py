from datetime import datetime
from uuid import NAMESPACE_DNS, uuid5

import pytz
from icalendar import Calendar, Event


def render_ical(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    appointment_id, participant_name, appointment_start, appointment_end, description
):
    """
    Render standard iCalendar file content.
    :param appointment_id: appointment id
    :param participant_name: the other party's name, for practitioner email this is member name
        and for member email, this is practitioner name
    :param appointment_start: scheduled start time
    :param appointment_end: scheduled end time
    :param description: calendar event description
    :return: ical file content in unicode
    """
    cal = Calendar()
    cal.add("version", "2.0")
    cal.add("prodid", "-//Maven Clinic Co//NONSGML Calendar v1.0//EN")

    event = Event()
    event.add("summary", f"Maven Appointment with {participant_name}")
    # use UUID5, ensure same appointment gets same UID within namespace
    event.add("uid", str(uuid5(NAMESPACE_DNS, str(appointment_id))))
    event.add("dtstamp", datetime.now(tz=pytz.utc))
    event.add("dtstart", appointment_start.replace(tzinfo=pytz.utc))
    event.add("dtend", appointment_end.replace(tzinfo=pytz.utc))
    event.add("description", description)
    cal.add_component(event)

    ical_content = cal.to_ical()
    if isinstance(ical_content, bytes):
        ical_content = ical_content.decode("utf-8")
    return ical_content
